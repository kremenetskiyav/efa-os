"""Conservative recommendations tied to delivery-date price intervals."""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from config import RecommendationConfig
from models import PriceWindow, ProductEconomics, Recommendation

MONEY = Decimal("0.01")
def _money(v: Decimal) -> Decimal: return v.quantize(MONEY, rounding=ROUND_HALF_UP)
def _margin(w: PriceWindow) -> Decimal | None: return _money(w.profit / w.revenue * 100) if w.revenue > 0 else None
def _ppu(w: PriceWindow) -> Decimal | None: return _money(w.profit / w.units) if w.units > 0 else None
def _confidence(w: PriceWindow, c: RecommendationConfig) -> str: return "high" if w.units >= c.min_window_units * 2 else "medium" if w.units >= c.min_window_units else "low"

def build_recommendation(e: ProductEconomics, c: RecommendationConfig) -> Recommendation:
    issues = list(e.data_issues)
    if e.current_price is None or e.current_price_since is None: issues.append("missing_current_price_context")
    if e.cost_price is None: issues.append("missing_cost_price")
    current = next((w for w in e.windows if w.seller_price == e.current_price and w.delivery_start >= e.current_price_since), None) if e.current_price_since else None
    if issues:
        return _result(e, current, "REVIEW_DATA", "high", None, "low", "REVIEW_DATA", tuple(sorted(set(issues))))
    if current is None or _confidence(current, c) == "low":
        return _result(e, None, "REVIEW_DATA", "medium", None, "low", "NOT_YET_CONFIRMED", ("current_price_has_no_sufficient_confirmed_deliveries",))
    margin, ppu = _margin(current), _ppu(current)
    if margin is None or ppu is None:
        return _result(e, current, "REVIEW_DATA", "high", None, "low", "REVIEW_DATA", ("invalid_current_unit_economics",))
    candidates = []
    for w in e.windows:
        if w is current or _confidence(w, c) == "low" or _margin(w) is None or _ppu(w) is None: continue
        if abs(w.seller_price / current.seller_price - 1) * 100 <= c.max_price_step_percent and _margin(w) >= c.low_margin_percent and _ppu(w) > ppu: candidates.append(w)
    if candidates:
        best = max(candidates, key=lambda w: (_ppu(w), -w.seller_price))
        action = "CONSIDER_RAISE" if best.seller_price > current.seller_price else "CONSIDER_LOWER"
        return _result(e, current, action, "medium", best, _confidence(best,c), "CONFIRMED", ("observed_delivery_price_interval_has_better_confirmed_unit_economics",))
    if margin < c.low_margin_percent:
        return _result(e,current,"CONSIDER_RAISE","medium",None,_confidence(current,c),"CONFIRMED",("current_margin_below_configured_threshold","no_confirmed_observed_price_candidate"))
    return _result(e,current,"KEEP","low",None,_confidence(current,c),"CONFIRMED",("current_price_economics_confirmed",))

def _result(e: ProductEconomics, current: PriceWindow | None, action: str, priority: str, candidate: PriceWindow | None, confidence: str, status: str, reasons: tuple[str,...]) -> Recommendation:
    last=e.last_confirmed
    return Recommendation(e.offer_id,e.current_price,current.effective_price if current else None,current.revenue if current else None,current.profit if current else None,_ppu(current) if current else None,_margin(current) if current else None,current.commission if current else None,current.logistics if current else None,current.other_expenses if current else None,current.delivery_start if current else None,current.delivery_end if current else None,action,priority,candidate.seller_price if candidate else None,_ppu(candidate) if candidate else None,_margin(candidate) if candidate else None,confidence,"valid" if status=="CONFIRMED" else "review",reasons,last.effective_price if last else None,last.delivery_end if last else None,_ppu(last) if last else None,_margin(last) if last else None,status,e.current_price_since)
