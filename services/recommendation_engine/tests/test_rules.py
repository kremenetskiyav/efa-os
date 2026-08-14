from datetime import datetime
from decimal import Decimal
import unittest
from config import RecommendationConfig
from models import PriceWindow, ProductEconomics
from rules import build_recommendation

C = RecommendationConfig(Decimal("15"), 10, Decimal("20"))
def w(price: str, *, units: int=12, start: int=1, end: int=2, profit: str="20") -> PriceWindow:
    revenue=Decimal(price)*units
    return PriceWindow(Decimal(price),Decimal(price),units,units,revenue,Decimal("-20")*units,Decimal("-10")*units,Decimal("0"),Decimal("40")*units,Decimal("0"),Decimal(profit)*units,datetime(2026,8,start),datetime(2026,8,end))
def p(*windows: PriceWindow, current: str="100", since: int=1) -> ProductEconomics:
    return ProductEconomics("УФ 005Б",Decimal(current),datetime(2026,8,since),Decimal("40"),windows,windows[-1] if windows else None)
class DeliveryDateRulesTests(unittest.TestCase):
    def test_delivery_before_price_change_even_if_recognized_later_is_not_current(self):
        r=build_recommendation(p(w("90",end=2),current="100",since=3),C)
        self.assertEqual((r.current_price_economics_status,r.action,r.proposed_price),("NOT_YET_CONFIRMED","REVIEW_DATA",None))
    def test_delivery_after_price_change_confirms_current_price(self):
        r=build_recommendation(p(w("100",start=3,end=4),current="100",since=3),C)
        self.assertEqual(r.current_price_economics_status,"CONFIRMED")
        self.assertEqual(r.action,"KEEP")
    def test_multiple_deliveries_in_one_interval_aggregate_in_one_window(self):
        r=build_recommendation(p(w("100",units=24,start=3,end=4),current="100",since=3),C)
        self.assertEqual((r.confidence,r.current_price_economics_status),("high","CONFIRMED"))
    def test_quality_gate_remains_review(self):
        e=ProductEconomics("УФ",Decimal("100"),datetime(2026,8,1),Decimal("40"),(w("100"),),None,("unallocated_other_expenses",))
        self.assertEqual(build_recommendation(e,C).current_price_economics_status,"REVIEW_DATA")
