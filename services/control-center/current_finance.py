"""Compatibility API plus retained LEGACY collector model (not an active provider).

Daily demand/physical volumes may be aggregated with complete day coverage.
Daily financial economics are never aggregated or renamed into period finance.
"""
from __future__ import annotations

import copy
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation


MOSCOW = timezone(timedelta(hours=3))
PRESETS = {'today': 'TODAY', 'yesterday': 'YESTERDAY', 'last7': 'LAST_7_DAYS',
           'last30': 'LAST_30_DAYS', 'this_month': 'CURRENT_MONTH',
           'previous_month': 'PREVIOUS_MONTH', 'august2026': 'AUGUST_2026'}
SKU_MAP = {f'УФ {i:03}Б': f'UF{i:03}' for i in range(1, 6)}
FIELDS = ('ordered_units', 'delivered_units', 'returned_units', 'ordered_revenue',
          'delivered_revenue', 'seller_realization', 'cogs', 'ozon_commission',
          'logistics', 'last_mile', 'processing', 'acquiring', 'advertising_cpc',
          'advertising_cpo', 'advertising_total', 'returns_adjustment',
          'compensations', 'other_costs', 'contribution_rub', 'contribution_pct',
          'profit_rub', 'profit_pct')
REQUIRED_COSTS = ('tax', 'historical_cogs', 'returns', 'settlement_adjustments',
                  'internal_costs', 'finance_costs', 'advertising')
LIVE_VOLUMES = {
    'ordered_units': ('demand_quality_status', 'demand_collected_at', 'order_date'),
    'ordered_revenue': ('demand_quality_status', 'demand_collected_at', 'order_date'),
    'delivered_units': ('postings_collection_status', 'postings_collected_at', 'delivery_date'),
    'returned_units': ('returns_collection_status', 'returns_collected_at', 'return_date'),
}
WARNINGS = [
    'PERIOD_FINANCE_SOURCE_UNAVAILABLE', 'NO_DAILY_FINANCIAL_SUMMATION',
    'SELLER_REALIZATION_MAPPING_UNCONFIRMED', 'PROFIT_INSUFFICIENT_DATA',
    'HISTORICAL_COGS_UNAVAILABLE', 'TAX_AND_INTERNAL_COSTS_UNAVAILABLE',
    'SETTLEMENT_ADJUSTMENTS_UNCONFIRMED', 'FINANCE_SIDE_ADVERTISING_UNAVAILABLE',
]


def decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def stamp(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result if result.tzinfo else None
    except (ValueError, TypeError):
        return None


def freshness(observed_at, now, failed=False):
    """Daily cadence verified in source history; 2h grace is explicit app policy."""
    observed = stamp(observed_at)
    if observed is None or observed > now:
        return 'NO_DATA'
    age = (now-observed).total_seconds()/3600
    return 'STALE' if age > 50 else 'DELAYED' if failed or age > 26 else 'FRESH'


def health(rows, status_key, time_key, now):
    valid = [(stamp(row.get(time_key)), row.get(status_key)) for row in rows]
    valid = [(at, state) for at, state in valid if at and at <= now]
    successful = [at for at, state in valid if state in ('SUCCESS', 'SUCCESS_ZERO', 'SUCCESS_NONZERO', 'valid')]
    last = max(successful).isoformat() if successful else None
    attempt = max(valid, key=lambda pair: pair[0]) if valid else (None, None)
    failed = attempt[1] not in ('SUCCESS', 'SUCCESS_ZERO', 'SUCCESS_NONZERO', 'valid', None)
    return {'status': freshness(last, now, failed), 'observed_at': last,
            'last_attempt_at': attempt[0].isoformat() if attempt[0] else None,
            'last_attempt_status': attempt[1], 'cadence_hours': 24,
            'delayed_after_hours': 26, 'stale_after_hours': 50,
            'threshold_basis': 'Observed daily runs; 2-hour application grace, one missed cycle before STALE'}


def blank_entity(period, source, now):
    partial = period['to'] == now.astimezone(MOSCOW).date().isoformat()
    status = 'PARTIAL_DAY' if partial else 'PROVISIONAL'
    missing = {'mode': 'INSUFFICIENT_DATA', 'source': None,
               'period': {'from': period['from'], 'to': period['to']},
               'freshness': 'NO_DATA', 'complete_costs': False,
               'settlement_status': status, 'reason': 'SOURCE_OR_SEMANTIC_MAPPING_UNAVAILABLE'}
    return {**dict.fromkeys(FIELDS), 'period_start': period['from'], 'period_end': period['to'],
            'mode': 'INSUFFICIENT_DATA', 'source': source, 'complete_costs': False,
            'cost_completeness': dict.fromkeys(REQUIRED_COSTS, False),
            'settlement_status': status,
            'data_freshness': 'NO_DATA', 'freshness': 'NO_DATA',
            'reconciliation_gap': None, 'reconciliation_gap_rub': None,
            'field_metadata': {field: copy.deepcopy(missing) for field in FIELDS}, 'warnings': list(WARNINGS)}


def enforce_profit(entity):
    allowed = (entity.get('complete_costs') is True
               and all(entity.get('cost_completeness', {}).get(key) is True for key in REQUIRED_COSTS)
               and entity.get('settlement_status') in ('FINAL_SETTLEMENT', 'CORRECTED_FINAL_SETTLEMENT')
               and entity.get('mode') == 'SETTLEMENT_AWARE')
    if not allowed:
        entity['profit_rub'] = entity['profit_pct'] = None
        if 'PROFIT_INSUFFICIENT_DATA' not in entity['warnings']:
            entity['warnings'].append('PROFIT_INSUFFICIENT_DATA')


def aggregate(rows, offers, days, key, now):
    status_key, time_key, cohort = LIVE_VOLUMES[key]
    indexed = {}
    duplicates = set()
    for row in rows:
        identity = (row.get('offer_id'), row.get('business_date'))
        if identity in indexed:
            duplicates.add(identity)
        indexed[identity] = row
    values, dates = [], []
    for offer in offers:
        for day in days:
            row = indexed.get((offer, day), {})
            value, observed = decimal(row.get(key)), stamp(row.get(time_key))
            good = row.get(status_key) in ('valid', 'SUCCESS', 'SUCCESS_ZERO', 'SUCCESS_NONZERO')
            if (good and value is not None and value >= 0 and observed and observed <= now
                    and (offer, day) not in duplicates
                    and (not key.endswith('_units') or value == value.to_integral_value())):
                values.append(value)
                dates.append(observed)
    expected = len(offers)*len(days)
    complete = len(values) == expected and expected > 0
    total = sum(values, Decimal(0)) if complete else None
    return (str(total) if total is not None else None), {
        'mode': 'OBSERVED' if complete else 'INSUFFICIENT_DATA', 'cohort': cohort,
        'expected_sku_days': expected, 'covered_sku_days': len(values),
        'observed_subtotal': str(sum(values, Decimal(0))) if values else None,
        'observed_at': max(dates).isoformat() if dates else None,
        'earliest_observed_at': min(dates).isoformat() if dates else None,
        'latest_observed_at': max(dates).isoformat() if dates else None,
        'freshness': freshness(max(dates).isoformat() if dates else None, now) if complete else 'NO_DATA',
        'source_freshness': freshness(max(dates).isoformat() if dates else None, now),
        'source': 'mcp_read.product_daily_performance',
        'complete_period': complete, 'complete_costs': False,
        'period': {'from': days[0], 'to': days[-1]},
        'settlement_status': 'PARTIAL_DAY' if days[-1] == now.astimezone(MOSCOW).date().isoformat() else 'PROVISIONAL',
    }


def reconciliation(portfolio, skus):
    rows = []
    for field in FIELDS:
        if field.endswith('_pct'):
            continue
        total = decimal(portfolio[field])
        values = [decimal(s[field]) for s in skus]
        def basis(entity):
            meta = entity.get('field_metadata', {}).get(field, {})
            return (entity['period_start'], entity['period_end'],
                    meta.get('mode', entity['mode']), meta.get('cohort'))
        comparable = bool(skus) and all(basis(s) == basis(portfolio) for s in skus)
        subtotal = sum(values, Decimal(0)) if comparable and all(v is not None for v in values) else None
        gap = total-subtotal if total is not None and subtotal is not None else None
        rows.append({'field': field, 'portfolio': str(total) if total is not None else None,
                     'sku_sum': str(subtotal) if subtotal is not None else None,
                     'gap': str(gap) if gap is not None else None,
                     'status': 'INSUFFICIENT_DATA' if gap is None else 'PASS' if gap == 0 else 'GAP',
                     'reason': 'INCOMPARABLE_BASIS' if not comparable else 'MISSING_VALUES' if gap is None else None})
    result = next(r for r in rows if r['field'] == 'contribution_rub')
    return {'fields': rows, 'reconciliation_gap_rub': result['gap'],
            'status': result['status'], 'gap_reasons': [], 'allocation_rule': 'NO_SYNTHETIC_ALLOCATION'}


def live_snapshot(period, payload, now):
    preset = PRESETS[period['id']]
    source = 'EFA Read MCP / mcp_read.product_daily_performance'
    portfolio = blank_entity(period, source, now)
    products = payload.get('products', [])
    identities = {}
    for offer in SKU_MAP:
        matches = [p for p in products if p.get('offer_id') == offer]
        if len(matches) == 1 and isinstance(matches[0].get('sku'), int):
            identities[offer] = matches[0]
    rows = [r for r in payload.get('daily', []) if r.get('offer_id') in identities]
    start, end = date.fromisoformat(period['from']), date.fromisoformat(period['to'])
    days = [(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
    skus = []
    for offer, internal in SKU_MAP.items():
        entity = blank_entity(period, source, now)
        entity.update(efa_sku=offer, sku=internal, ozon_sku=identities.get(offer, {}).get('sku'))
        if days:
            for field in LIVE_VOLUMES:
                entity[field], entity['field_metadata'][field] = aggregate(rows, [offer], days, field, now)
        entity['current_cost_evidence'] = {key: identities.get(offer, {}).get(key)
                                           for key in ('cost_price', 'cost_basis', 'product_observed_at')}
        # Unit current cost is evidence, not historical total COGS.
        skus.append(entity)
    if days:
        for field in LIVE_VOLUMES:
            portfolio[field], portfolio['field_metadata'][field] = aggregate(
                rows, list(SKU_MAP), days, field, now)
    source_health = {key: health(payload.get('daily', []), status, at, now) for key, status, at in (
        ('finance', 'finance_collection_status', 'finance_collected_at'),
        ('demand', 'demand_quality_status', 'demand_collected_at'),
        ('postings', 'postings_collection_status', 'postings_collected_at'),
        ('returns', 'returns_collection_status', 'returns_collected_at'))}
    source_health['cpc'] = health(payload.get('cpc', []), 'collection_status', 'observed_at', now)
    recon = reconciliation(portfolio, skus)
    for entity in [portfolio, *skus]:
        entity['data_freshness'] = entity['freshness'] = source_health['finance']['status']
        enforce_profit(entity)
    warnings = list(WARNINGS)
    for name, state in source_health.items():
        if state['last_attempt_status'] in ('FAILED', 'STUCK', 'PENDING'):
            warnings.append(name.upper()+'_COLLECTION_'+state['last_attempt_status'])
    if payload.get('errors'):
        warnings.append('SOURCE_READ_UNAVAILABLE')
    if len(identities) != 5:
        warnings.append('SKU_MAPPING_INCOMPLETE')
    campaign = [r for r in payload.get('cpc', []) if r.get('business_date') in days]
    return {'schema_version': 'efa_finance_snapshot_v1', 'portfolio': portfolio, 'skus': skus,
            'metadata': {'preset': preset, 'period_start': period['from'], 'period_end': period['to'],
                         'timezone': 'Europe/Moscow', 'generated_at': now.isoformat(),
                         'fetched_at': payload.get('fetched_at'),
                         'transport': payload.get('transport'), 'source_health': source_health,
                         'source_errors': payload.get('errors', {}),
                         'period_finance_available': False, 'profit_available': False,
                         'daily_finance_aggregation': 'FORBIDDEN',
                         'campaign_metrics': {'classification': 'ANALYTICAL_EVIDENCE_ONLY', 'rows': campaign,
                                              'combo_model': 'UNCONFIRMED', 'finance_charge_priority': True}},
            'warnings': warnings, 'reconciliation': recon}


HISTORICAL_MAP = {'ordered_units': 'ordered_units', 'delivered_units': 'delivered_units',
    'returned_units': 'returned_units', 'ordered_revenue': 'ordered_revenue',
    'seller_realization': 'seller_realization', 'cogs': 'cogs', 'ozon_commission': 'commission',
    'logistics': 'logistics', 'last_mile': 'last_mile', 'processing': 'processing', 'acquiring': 'acquiring',
    'advertising_total': 'advertising', 'other_costs': 'other_costs',
    'contribution_rub': 'contribution', 'contribution_pct': 'margin'}


def historical_snapshot(view, payload, now):
    snap = live_snapshot(view['period'], payload, now)
    snap['metadata'].update(transport='W06_HISTORICAL_REPORT', historical_reference=True,
                            period_finance_available=view['available'],
                            source_health={}, campaign_metrics={'classification': 'NOT_USED_FOR_HISTORICAL_REFERENCE'},
                            source_errors={}, fetched_at=None)
    entities = [snap['portfolio'], *snap['skus']]
    metrics = [view['portfolio'], *(s['metrics'] for s in view['skus'])]
    for entity, source in zip(entities, metrics):
        entity.update(dict.fromkeys(FIELDS))
        entity['field_metadata'] = blank_entity(view['period'], entity['source'], now)['field_metadata']
        entity['mode'] = 'SELLER_SIDE_PROXY' if view['available'] else 'INSUFFICIENT_DATA'
        entity['source'] = source['contribution']['source']
        entity['data_freshness'] = entity['freshness'] = 'HISTORICAL_REFERENCE'
        entity['settlement_status'] = 'PROVISIONAL'
        for target, original in HISTORICAL_MAP.items():
            entity[target] = source[original]['value']
            entity['field_metadata'][target] = copy.deepcopy(source[original])
            entity['field_metadata'][target].update(complete_costs=False, settlement_status='PROVISIONAL')
        entity['warnings'] = ['HISTORICAL_REFERENCE', 'PROFIT_INSUFFICIENT_DATA', 'COSTS_INCOMPLETE']
        enforce_profit(entity)
    # Only matched CPC is present in the per-SKU report; CPO stays unallocated.
    for sku in snap['skus']:
        sku['advertising_cpc'] = sku['advertising_total']
        sku['field_metadata']['advertising_cpc'] = copy.deepcopy(sku['field_metadata']['advertising_total'])
    components = view.get('advertising_components', {})
    snap['portfolio']['advertising_cpc'] = components.get('cpc')
    snap['portfolio']['advertising_cpo'] = components.get('cpo')
    for field in ('advertising_cpc', 'advertising_cpo'):
        if snap['portfolio'][field] is not None:
            snap['portfolio']['field_metadata'][field] = copy.deepcopy(snap['portfolio']['field_metadata']['advertising_total'])
    recon = reconciliation(snap['portfolio'], snap['skus'])
    bridge = view.get('bridge', {})
    recon['gap_reasons'] = [
        {'reason': 'UNALLOCATED_ADVERTISING', 'amount_rub': bridge.get('unallocated_advertising')},
        {'reason': 'ACCOUNT_LEVEL_CHARGE', 'amount_rub': bridge.get('unallocated_other')},
        {'reason': 'PREMIUM_EXCLUDED_FROM_CONTRIBUTION', 'amount_rub': view['portfolio']['premium']['value']},
    ]
    recon['unexplained_gap_rub'] = bridge.get('unexplained_difference')
    snap['reconciliation'] = recon
    snap['portfolio']['reconciliation_gap'] = snap['portfolio']['reconciliation_gap_rub'] = recon['reconciliation_gap_rub']
    snap['warnings'] = ['HISTORICAL_REFERENCE', 'PROFIT_INSUFFICIENT_DATA', *view['data_gaps']]
    return snap


class FinanceService:
    def __init__(self, factory=None, ttl=60):
        self.factory = factory
        self.ttl = ttl
        self.lock = threading.Lock()
        self.cached = None
        self.key = None
        self.cached_at = 0

    def source_data(self, options, now):
        from finance_source import McpFinanceSource, SourceUnavailable  # archived provider only
        start = min(date.fromisoformat(p['from']) for p in options if p['id'] != 'august2026')
        end = now.astimezone(MOSCOW).date()
        key = (start, end, os.getenv('EFA_FINANCE_SOURCE', 'disabled'))
        with self.lock:
            if self.key == key and self.cached is not None and time.monotonic()-self.cached_at < self.ttl:
                return copy.deepcopy(self.cached)
            try:
                if self.factory:
                    source = self.factory()
                elif key[2] == 'mcp':
                    source = McpFinanceSource()
                else:
                    raise SourceUnavailable('FINANCE_SOURCE_NOT_CONFIGURED')
                payload = source.fetch(start, end)
            except Exception as exc:
                code = str(exc) if isinstance(exc, SourceUnavailable) else 'SOURCE_UNAVAILABLE'
                payload = {'products': [], 'daily': [], 'cpc': [], 'errors': {'connection': code}}
            payload['fetched_at'] = now.isoformat()
            self.key, self.cached, self.cached_at = key, copy.deepcopy(payload), time.monotonic()
            return payload


SERVICE = FinanceService()


def attach_legacy(finance, now, service=None):
    """Adapt the new contract to the accepted V3 layout without changing its structure."""
    from finance_model import blank, metric, reconcile
    payload = (service or SERVICE).source_data(finance['periods'], now)
    snapshots = {}
    for period in finance['periods']:
        key = period['id']
        if key == 'august2026':
            snap = historical_snapshot(finance['views'][key], payload, now)
        else:
            snap = live_snapshot(period, payload, now)
            view = blank(period)
            for target, entity in zip([view['portfolio'], *(s['metrics'] for s in view['skus'])],
                                      [snap['portfolio'], *snap['skus']]):
                for datum in target.values():
                    datum.update(mode='INSUFFICIENT_DATA', complete_costs=False,
                                 settlement_status=entity['settlement_status'])
                for field in LIVE_VOLUMES:
                    meta = entity['field_metadata'][field]
                    datum = metric(entity[field], period, source='finance-snapshot/'+PRESETS[key],
                                   mode=meta['mode'], observed_at=meta['observed_at'], cohort=meta['cohort'],
                                   scope='Наблюдаемые данные за выбранные даты; неполная выборка не суммируется в полный итог.')
                    datum.update(freshness=meta['freshness'], complete_costs=False,
                                 settlement_status=entity['settlement_status'], source_detail=meta)
                    target[field] = datum
            view['available'] = any(v['value'] is not None for v in view['portfolio'].values())
            view['data_gaps'] = ['Нет текущих финансовых данных. Доступные заказы и физические объёмы показаны отдельно.',
                                 'Прибыль не подтверждена: периодный финансовый источник и полнота расходов недоступны.']
            view['reconciliation'] = reconcile(view)
            finance['views'][key] = view
        snapshots[PRESETS[key]] = snap
    finance['snapshots'] = snapshots
    finance['default_period'] = 'this_month'
    finance['data_gaps'] = ['Периодная финансовая функция недоступна через текущий MCP; дневная экономика не суммируется.']
    for period in finance['periods']:
        snap = snapshots[PRESETS[period['id']]]
        finance['views'][period['id']]['current_snapshot_metadata'] = snap['metadata']
        finance['views'][period['id']]['current_snapshot_warnings'] = snap['warnings']
    return finance


def get_snapshot(root, preset='CURRENT_MONTH', now=None):
    from w06_snapshot import build
    if preset not in PRESETS.values():
        raise ValueError('INVALID_FINANCE_PERIOD')
    now = now or datetime.now(timezone.utc)
    return build(root, now)['snapshots'][preset]
