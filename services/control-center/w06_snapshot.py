"""W06 local output contract and read-only presentation adapter. No source collection.

W06 owns amounts, reconciliation and freshness validity. Readers validate and copy;
they never derive revenue, advertising, contribution or profit from other fields.
"""
from __future__ import annotations

import copy
import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCHEMA = 'efa_w06_finance_snapshot.v1'
PRESETS = {'today': 'TODAY', 'yesterday': 'YESTERDAY', 'last7': 'LAST_7_DAYS',
           'last30': 'LAST_30_DAYS', 'this_month': 'CURRENT_MONTH',
           'previous_month': 'PREVIOUS_MONTH', 'august2026': 'AUGUST_2026'}
FIELDS = ('ordered_units', 'delivered_units', 'returned_units',
          'buyer_returned_units', 'logistic_return_units', 'ordered_revenue',
          'seller_realization', 'cogs', 'ozon_commission', 'logistics', 'last_mile',
          'processing', 'acquiring', 'advertising_cpc', 'advertising_cpo',
          'advertising_total', 'compensations', 'other_costs', 'contribution_rub',
          'contribution_pct', 'profit_rub', 'profit_pct')
IDENTITIES = dict(zip((f'УФ {i:03}Б' for i in range(1, 6)),
                     (4601821825, 4642158029, 4671345564, 4642180551, 4671328307)))
MODES = {'OBSERVED', 'SETTLEMENT_AWARE', 'SELLER_SIDE_PROXY',
         'MIXED_OBSERVED_PROXY', 'INSUFFICIENT_DATA'}
FINAL = {'FINAL_SETTLEMENT', 'CORRECTED_FINAL_SETTLEMENT'}
LAYERS = ('demand', 'operational_economics', 'account_finance', 'cost', 'settlement')
COMPARISON_CLASSES = {'TRUE_DATA_CONFLICT', 'SEMANTIC_SOURCE_DIFFERENCE',
                      'UNRESOLVED_BUT_SEMANTICALLY_EXPLAINABLE'}
COST_COVERAGE = ('tax', 'historical_cogs', 'returns', 'settlement_adjustments',
                 'internal_costs', 'finance_costs', 'advertising')
MESSAGES = {'MISSING': 'Финансовый отчёт W06 ещё не сформирован',
            'STALE': 'Финансовый отчёт требует обновления',
            'INVALID': 'Финансовый отчёт W06 не прошёл проверку',
            'UNKNOWN': 'Срок актуальности финансового evidence не утверждён',
            'INSUFFICIENT_DATA': 'В отчёте W06 недостаточно данных за выбранный период'}


def instant(value):
    if not isinstance(value, str):
        raise ValueError('TIMESTAMP_REQUIRED')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('TIMEZONE_REQUIRED')
    return result


def number(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('INVALID_NUMBER')
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('INVALID_NUMBER') from exc
    if not result.is_finite():
        raise ValueError('NONFINITE_NUMBER')
    return result


def directory(root):
    return Path(root) / 'REPORTS/W06/SNAPSHOTS'


def empty(period, now, reason='MISSING'):
    entity = {**dict.fromkeys(FIELDS), 'field_metadata': {
        field: {'semantic': field, 'source': None, 'source_timestamp': None,
                'confidence': 'UNKNOWN', 'financial_mode': 'INSUFFICIENT_DATA'}
        for field in FIELDS}, 'complete_costs': False}
    layers = {name: {'source_status': 'INSUFFICIENT_DATA',
                     'financial_mode': 'INSUFFICIENT_DATA',
                     'freshness': 'NO_DATA', 'confidence': 'UNKNOWN',
                     'date_basis': None, 'cohort_basis': None, 'source': None}
              for name in LAYERS}
    return {'schema': SCHEMA, 'generated_at': now.isoformat(),
            'period': {'preset': PRESETS[period['id']], 'from': period['from'],
                       'to': period['to'], 'timezone': 'Europe/Moscow'},
            'source_status': 'INSUFFICIENT_DATA', 'financial_mode': 'INSUFFICIENT_DATA',
            'settlement_status': 'INSUFFICIENT_SETTLEMENT_DATA',
            'freshness': {'status': 'NO_DATA', 'observed_at': None, 'valid_until': None},
            'layers': layers, 'source_comparisons': [],
            'portfolio': copy.deepcopy(entity),
            'skus': [{**copy.deepcopy(entity), 'efa_sku': sku, 'ozon_sku': ozon,
                      'commercial_role': None, 'financial_gate': 'INSUFFICIENT_DATA'}
                     for sku, ozon in IDENTITIES.items()],
            'reconciliation': {'status': 'INSUFFICIENT_DATA', 'fields': [
                {'field': f, 'portfolio': None, 'sku_sum': None, 'gap': None,
                 'status': 'INSUFFICIENT_DATA'} for f in ('seller_realization', 'advertising_total', 'contribution_rub')],
                               'reconciliation_gap_rub': None, 'gap_reasons': []},
            'warnings': [MESSAGES.get(reason, reason)], 'evidence': []}


def normalize_legacy_safe_missing(snapshot):
    """Read-only compatibility; never promotes a legacy value to a V2 semantic."""
    entities = [snapshot.get('portfolio'), *snapshot.get('skus', [])]
    if snapshot.get('schema') != SCHEMA or not entities or any(
            not isinstance(entity, dict) for entity in entities):
        return snapshot
    result = copy.deepcopy(snapshot)
    legacy_v1 = 'layers' not in result or 'source_comparisons' not in result
    legacy_source_times = {
        item.get('source'): item.get('source_timestamp') or item.get('observed_at')
        for item in result.get('evidence', []) if isinstance(item, dict)
    }
    for entity in [result['portfolio'], *result['skus']]:
        for field in FIELDS:
            entity.setdefault(field, None)
        field_metadata = entity.setdefault('field_metadata', {})
        for field in FIELDS:
            field_metadata.setdefault(field, {
                'semantic': field, 'source': None, 'source_timestamp': None,
                'confidence': 'UNKNOWN', 'financial_mode': 'INSUFFICIENT_DATA'})
            meta = field_metadata[field]
            if legacy_v1:
                meta.setdefault('source_timestamp', legacy_source_times.get(meta.get('source')))
                meta.setdefault('confidence', 'LOW' if result.get('financial_mode') == 'SELLER_SIDE_PROXY' else 'UNKNOWN')
                meta.setdefault('financial_mode', (result.get('financial_mode', 'INSUFFICIENT_DATA')
                                                   if entity.get(field) is not None
                                                   else 'INSUFFICIENT_DATA'))
                if field.startswith('contribution_') and entity.get(field) is not None \
                        and meta['financial_mode'] == 'SELLER_SIDE_PROXY':
                    meta.setdefault('missing_components', [
                        'historical_effective_cogs', 'tax', 'settlement_adjustments'])
        if legacy_v1 and entity.get('returned_units') is not None:
            entity['returned_units'] = None
            field_metadata['returned_units'] = {
                'semantic': 'returned_units', 'source': None, 'source_timestamp': None,
                'confidence': 'UNKNOWN', 'financial_mode': 'INSUFFICIENT_DATA',
                'missing_reason': 'LEGACY_GENERIC_RETURN_NOT_CANONICAL_IN_V2'}
    for item in result.get('evidence', []):
        item.setdefault('source_timestamp', item.get('observed_at'))
    result.setdefault('layers', {
        name: {'source_status': 'INSUFFICIENT_DATA',
               'financial_mode': 'INSUFFICIENT_DATA', 'freshness': 'NO_DATA',
               'confidence': 'UNKNOWN', 'date_basis': None,
               'cohort_basis': None, 'source': None}
        for name in LAYERS})
    result.setdefault('source_comparisons', [])
    if legacy_v1:
        reconciliation = result.get('reconciliation')
        if isinstance(reconciliation, dict) and isinstance(reconciliation.get('fields'), list):
            reconciliation['fields'] = [
                row for row in reconciliation['fields']
                if row.get('field') != 'returned_units']
        result.setdefault('warnings', []).append(
            'LEGACY_V1_READ_COMPATIBILITY_SPLIT_RETURNS_UNAVAILABLE')
        if result.get('settlement_status') == 'INSUFFICIENT_SETTLEMENT_DATA' \
                and not any('INSUFFICIENT_SETTLEMENT_DATA' in warning
                            for warning in result['warnings']):
            result['warnings'].append('INSUFFICIENT_SETTLEMENT_DATA')
    return result


def validate(snapshot, now):
    """Fail closed on malformed, misattributed or settlement-unsafe documents."""
    required = {'schema', 'generated_at', 'period', 'source_status', 'financial_mode',
                'settlement_status', 'freshness', 'portfolio', 'skus',
                'layers', 'source_comparisons', 'reconciliation', 'warnings', 'evidence'}
    if not isinstance(snapshot, dict) or not required <= snapshot.keys() or snapshot['schema'] != SCHEMA:
        raise ValueError('SCHEMA_MISMATCH')
    generated = instant(snapshot['generated_at'])
    if generated > now:
        raise ValueError('FUTURE_SNAPSHOT')
    p = snapshot['period']
    if p['preset'] not in PRESETS.values() or p['timezone'] != 'Europe/Moscow':
        raise ValueError('PERIOD_MISMATCH')
    start, end = date.fromisoformat(p['from']), date.fromisoformat(p['to'])
    if start.isoformat() != p['from'] or end.isoformat() != p['to'] or end < start:
        raise ValueError('INVALID_PERIOD')
    if snapshot['financial_mode'] not in MODES or snapshot['source_status'] not in {'AVAILABLE', 'PARTIAL', 'INSUFFICIENT_DATA'}:
        raise ValueError('INVALID_MODE')
    if snapshot['settlement_status'] not in FINAL | {'INSUFFICIENT_SETTLEMENT_DATA'}:
        raise ValueError('SETTLEMENT_STATUS_REQUIRED')
    fresh = snapshot['freshness']
    if fresh['status'] not in {'FRESH', 'STALE', 'UNKNOWN', 'NO_DATA', 'HISTORICAL_REFERENCE'}:
        raise ValueError('INVALID_FRESHNESS')
    observed = instant(fresh['observed_at']) if fresh['observed_at'] is not None else None
    until = instant(fresh['valid_until']) if fresh['valid_until'] is not None else None
    if observed and observed > generated or until and (not observed or until < observed):
        raise ValueError('INVALID_FRESHNESS_TIME')
    if fresh['status'] in {'FRESH', 'STALE'} and (not observed or not until):
        raise ValueError('W06_VALIDITY_REQUIRED')
    if fresh['status'] == 'HISTORICAL_REFERENCE' and (p['preset'] != 'AUGUST_2026' or (p['from'], p['to']) != ('2026-08-01', '2026-08-31')):
        raise ValueError('HISTORICAL_SCOPE_MISMATCH')
    if not isinstance(snapshot['warnings'], list) or not all(isinstance(w, str) for w in snapshot['warnings']):
        raise ValueError('WARNINGS_REQUIRED')
    evidence = snapshot['evidence']
    if not isinstance(evidence, list) or not all(
            isinstance(e, dict) and isinstance(e.get('source'), str) and e['source']
            and 'source_timestamp' in e and 'confirmation' in e and 'limitation' in e
            and isinstance(e['confirmation'], str) and isinstance(e['limitation'], str)
            for e in evidence):
        raise ValueError('EVIDENCE_REQUIRED')
    for item in evidence:
        source_time = instant(item['source_timestamp']) if item['source_timestamp'] is not None else None
        if source_time and source_time > generated:
            raise ValueError('FUTURE_EVIDENCE')
    refs = {e['source'] for e in evidence}
    layers = snapshot['layers']
    if not isinstance(layers, dict) or set(layers) != set(LAYERS):
        raise ValueError('FINANCIAL_LAYERS_REQUIRED')
    for name, layer in layers.items():
        if not isinstance(layer, dict) or set(layer) != {
                'source_status', 'financial_mode', 'freshness', 'confidence',
                'date_basis', 'cohort_basis', 'source'}:
            raise ValueError('FINANCIAL_LAYER_FIELDS_REQUIRED')
        if layer['source_status'] not in {'AVAILABLE', 'PARTIAL', 'INCOMPLETE', 'INSUFFICIENT_DATA'} \
                or layer['financial_mode'] not in MODES \
                or layer['freshness'] not in {'FRESH', 'STALE', 'UNKNOWN', 'NO_DATA', 'HISTORICAL_REFERENCE'} \
                or layer['confidence'] not in {'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'}:
            raise ValueError('FINANCIAL_LAYER_CLASSIFICATION')
        if layer['source'] is not None and layer['source'] not in refs:
            raise ValueError('FINANCIAL_LAYER_PROVENANCE')
    comparisons = snapshot['source_comparisons']
    if not isinstance(comparisons, list):
        raise ValueError('SOURCE_COMPARISONS_REQUIRED')
    for item in comparisons:
        required_comparison = {'metric', 'source_a', 'value_a', 'basis_a',
                               'source_b', 'value_b', 'basis_b', 'classification',
                               'unresolved_reason'}
        if not isinstance(item, dict) or not required_comparison <= item.keys() \
                or item['classification'] not in COMPARISON_CLASSES \
                or item['source_a'] not in refs or item['source_b'] not in refs \
                or not isinstance(item['basis_a'], dict) or not isinstance(item['basis_b'], dict):
            raise ValueError('SOURCE_COMPARISON_INVALID')
        number(item['value_a'])
        number(item['value_b'])
    skus = snapshot['skus']
    if not isinstance(skus, list) or len(skus) != 5 or {s['efa_sku'] for s in skus} != set(IDENTITIES):
        raise ValueError('FIVE_SKUS_REQUIRED')
    for sku in skus:
        if sku['ozon_sku'] != IDENTITIES[sku['efa_sku']] or 'commercial_role' not in sku or not isinstance(sku.get('financial_gate'), str):
            raise ValueError('SKU_IDENTITY_OR_GATE')
    for entity in [snapshot['portfolio'], *skus]:
        if not isinstance(entity, dict) or not set(FIELDS) <= entity.keys():
            raise ValueError('FINANCIAL_FIELDS_REQUIRED')
        for key, datum in entity.get('presentation_metrics', {}).items():
            if key not in {'net_sold_units', 'return_logistics', 'return_processing',
                           'ozon_expenses', 'contribution_before_ads', 'margin_before_ads',
                           'premium', 'tax', 'corrections', 'proxy_result'}:
                raise ValueError('PRESENTATION_OVERRIDE_FORBIDDEN')
            number(datum['value'])
            if datum.get('source') not in refs or datum.get('period') != {'from': p['from'], 'to': p['to']}:
                raise ValueError('PRESENTATION_PROVENANCE_REQUIRED')
            if key == 'proxy_result' and number(datum['value']) != number(entity['contribution_rub']):
                raise ValueError('UNSUPPORTED_PROXY_RESULT')
        for field in FIELDS:
            amount = number(entity[field])
            meta = entity.get('field_metadata', {}).get(field)
            if not isinstance(meta, dict) or meta.get('semantic') != field:
                raise ValueError('FIELD_METADATA_REQUIRED')
            if meta.get('confidence') not in {'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'} \
                    or meta.get('financial_mode') not in MODES:
                raise ValueError('FIELD_CLASSIFICATION_REQUIRED')
            source = meta.get('source')
            source_time = meta.get('source_timestamp')
            if source is None:
                if source_time is not None:
                    raise ValueError('FIELD_SOURCE_TIME_WITHOUT_SOURCE')
            elif source not in refs or source_time is None or instant(source_time) > generated:
                raise ValueError('FIELD_PROVENANCE_REQUIRED')
            if amount is None:
                if meta['financial_mode'] != 'INSUFFICIENT_DATA':
                    raise ValueError('NULL_FIELD_MODE_REQUIRED')
                continue
            if field == 'returned_units':
                raise ValueError('GENERIC_RETURNED_UNITS_FORBIDDEN')
            if field.endswith('_units') and (amount < 0 or amount != amount.to_integral_value()):
                raise ValueError('INVALID_UNITS')
            if source is None or meta['financial_mode'] == 'INSUFFICIENT_DATA':
                raise ValueError('FIELD_PROVENANCE_REQUIRED')
            if field == 'seller_realization' and meta.get('basis') != 'SELLER_REALIZATION':
                raise ValueError('BUYER_PRICE_SUBSTITUTION_FORBIDDEN')
            if field.startswith('contribution_') and meta['financial_mode'] == 'SELLER_SIDE_PROXY' \
                    and not meta.get('missing_components'):
                raise ValueError('PROXY_MISSING_COMPONENTS_REQUIRED')
            if field.startswith('profit_') and not (
                    snapshot['settlement_status'] in FINAL
                    and snapshot['financial_mode'] == 'SETTLEMENT_AWARE'
                    and entity.get('complete_costs') is True
                    and all(entity.get('cost_completeness', {}).get(k) is True for k in COST_COVERAGE)):
                raise ValueError('UNCONFIRMED_PROFIT')
    recon = snapshot['reconciliation']
    if not isinstance(recon, dict) or recon.get('status') not in {'PASS', 'GAP', 'INSUFFICIENT_DATA'} or not isinstance(recon.get('fields'), list):
        raise ValueError('RECONCILIATION_REQUIRED')
    seen = set()
    for row in recon['fields']:
        if row['field'] not in FIELDS or row['field'] in seen or row['status'] not in {'PASS', 'GAP', 'INSUFFICIENT_DATA'}:
            raise ValueError('RECONCILIATION_FIELD')
        seen.add(row['field'])
        for key in ('portfolio', 'sku_sum', 'gap'):
            number(row[key])
        if row['status'] == 'PASS' and number(row['gap']) != 0:
            raise ValueError('FALSE_RECONCILIATION_PASS')
    if recon['status'] == 'PASS' and (not recon['fields'] or any(r['status'] != 'PASS' for r in recon['fields'])):
        raise ValueError('FALSE_RECONCILIATION_PASS')
    return snapshot


def audit(snapshot, now):
    """W07 structural/reconciliation audit; never derives business economics."""
    validate(snapshot, now)
    for row in snapshot['reconciliation']['fields']:
        field = row['field']
        total = number(snapshot['portfolio'][field])
        parts = [number(s[field]) for s in snapshot['skus']]
        if number(row['portfolio']) != total:
            raise ValueError('RECONCILIATION_PORTFOLIO_MISMATCH')
        if all(v is not None for v in parts):
            subtotal = sum(parts, Decimal(0))
            if number(row['sku_sum']) != subtotal:
                raise ValueError('RECONCILIATION_SKU_SUM_MISMATCH')
            if total is not None and number(row['gap']) != total - subtotal:
                raise ValueError('RECONCILIATION_GAP_MISMATCH')
        if row['status'] == 'PASS' and (total is None or any(v is None for v in parts)):
            raise ValueError('RECONCILIATION_INCOMPLETE_PASS')
    fresh = snapshot['freshness']
    status = fresh['status']
    if status == 'FRESH' and instant(fresh['valid_until']) <= now:
        status = 'STALE'
    classes = {item['classification'] for item in snapshot['source_comparisons']}
    portfolio = snapshot['portfolio']
    skus = snapshot['skus']
    proxy_present = portfolio['contribution_rub'] is not None
    proxy_valid = False
    if proxy_present:
        expense_fields = ('ozon_commission', 'acquiring', 'logistics',
                          'processing', 'last_mile', 'other_costs')
        before_values = []
        proxy_valid = (
            portfolio['profit_rub'] is None and portfolio['profit_pct'] is None
            and all(sku['contribution_rub'] is None
                    and sku['contribution_pct'] is None
                    and sku['profit_rub'] is None and sku['profit_pct'] is None
                    for sku in skus)
            and all(sku[field] is None for sku in skus
                    for field in ('advertising_cpc', 'advertising_cpo',
                                  'advertising_total'))
            and portfolio['field_metadata']['contribution_rub'].get('financial_mode') == 'SELLER_SIDE_PROXY'
            and portfolio['field_metadata']['contribution_rub'].get('advertising_application') == 'PORTFOLIO_ONLY_ONCE')
        for sku in skus:
            realization = number(sku['seller_realization'])
            cogs = number(sku['cogs'])
            expenses = [number(sku[field]) for field in expense_fields]
            cogs_meta = sku['field_metadata']['cogs']
            realization_meta = sku['field_metadata']['seller_realization']
            per_unit = number(cogs_meta.get('current_cogs_per_unit'))
            quantity = cogs_meta.get('quantity_basis_used')
            reported = number(sku.get('presentation_metrics', {})
                              .get('contribution_before_ads', {}).get('value'))
            reported_margin = number(sku.get('presentation_metrics', {})
                                     .get('margin_before_ads', {}).get('value'))
            compatible = (
                cogs_meta.get('financial_mode') == 'SELLER_SIDE_PROXY'
                and cogs_meta.get('basis') == 'CURRENT_COGS_PROXY'
                and cogs_meta.get('cohort_basis') == realization_meta.get('cohort_basis')
                and isinstance(quantity, int) and quantity >= 0
                and per_unit is not None and cogs == per_unit * quantity
                and realization is not None and cogs is not None
                and all(value is not None for value in expenses))
            expected = (realization - sum(expenses, Decimal(0)) - cogs
                        if compatible else None)
            expected_margin = (expected / realization * Decimal(100)
                               if expected is not None and realization > 0 else None)
            margin_valid = (reported_margin is None and expected_margin is None) or (
                reported_margin is not None and expected_margin is not None
                and abs(reported_margin - expected_margin) <= Decimal('0.01'))
            proxy_valid = proxy_valid and compatible and reported == expected and margin_valid
            if reported is not None:
                before_values.append(reported)
        advertising = number(portfolio['advertising_total'])
        expected_portfolio = (sum(before_values, Decimal(0)) - advertising
                              if len(before_values) == len(skus)
                              and advertising is not None else None)
        portfolio_before = number(portfolio.get('presentation_metrics', {})
                                  .get('contribution_before_ads', {}).get('value'))
        portfolio_realization = number(portfolio['seller_realization'])
        portfolio_margin = number(portfolio['contribution_pct'])
        expected_margin = (expected_portfolio / portfolio_realization * Decimal(100)
                           if expected_portfolio is not None
                           and portfolio_realization is not None
                           and portfolio_realization > 0 else None)
        margin_valid = (portfolio_margin is None and expected_margin is None) or (
            portfolio_margin is not None and expected_margin is not None
            and abs(portfolio_margin - expected_margin) <= Decimal('0.01'))
        proxy_valid = (proxy_valid
                       and portfolio_before == sum(before_values, Decimal(0))
                       and number(portfolio['contribution_rub']) == expected_portfolio
                       and margin_valid)
    all_results_null = all(entity[field] is None
                           for entity in [portfolio, *skus]
                           for field in ('contribution_rub', 'contribution_pct',
                                         'profit_rub', 'profit_pct'))
    if 'TRUE_DATA_CONFLICT' in classes:
        audit_result = 'TRUE_DATA_CONFLICT'
    elif snapshot['source_status'] == 'PARTIAL':
        settlement_disclosed = (snapshot['settlement_status'] != 'INSUFFICIENT_SETTLEMENT_DATA'
                                or any('INSUFFICIENT_SETTLEMENT_DATA' in warning
                                       for warning in snapshot['warnings']))
        partial_results_safe = (snapshot['financial_mode'] != 'MIXED_OBSERVED_PROXY'
                                or all_results_null or proxy_valid)
        audit_result = ('PARTIAL_VALID' if settlement_disclosed and partial_results_safe
                        else 'STRUCTURAL_FAIL')
    elif classes & {'SEMANTIC_SOURCE_DIFFERENCE',
                    'UNRESOLVED_BUT_SEMANTICALLY_EXPLAINABLE'}:
        audit_result = 'SEMANTIC_SOURCE_DIFFERENCE'
    else:
        audit_result = 'PASS'
    return {'schema': 'PASS', 'period': 'PASS', 'freshness': status,
            'source_provenance': 'PASS', 'buyer_price_exclusion': 'PASS',
            'contribution_profit_semantics': 'PASS',
            'contribution_proxy': ('PASS' if proxy_valid else
                                   'NOT_APPLICABLE' if not proxy_present else 'FAIL'),
            'audit_result': audit_result,
            'blocker': ('PARTIAL_SEMANTICS_INVALID'
                        if audit_result == 'STRUCTURAL_FAIL' else None),
            'reconciliation': snapshot['reconciliation']['status'],
            'financial_mode': snapshot['financial_mode'],
            'settlement_status': snapshot['settlement_status'],
            'evidence_truth': 'SOURCE_REVIEW_COMPLETED_BY_W06'}


def audit_outcome(snapshot, now):
    """Return the complete W07 result vocabulary without weakening strict audit()."""
    try:
        return audit(snapshot, now)
    except (ValueError, KeyError, TypeError, OverflowError, AttributeError) as exc:
        return {'schema': 'FAIL', 'period': 'NOT_CONFIRMED',
                'freshness': 'UNKNOWN', 'source_provenance': 'NOT_CONFIRMED',
                'buyer_price_exclusion': 'NOT_CONFIRMED',
                'contribution_profit_semantics': 'NOT_CONFIRMED',
                'audit_result': 'STRUCTURAL_FAIL',
                'reconciliation': 'NOT_CONFIRMED',
                'financial_mode': snapshot.get('financial_mode') if isinstance(snapshot, dict) else None,
                'settlement_status': snapshot.get('settlement_status') if isinstance(snapshot, dict) else None,
                'evidence_truth': 'NOT_CONFIRMED', 'blocker': str(exc)}


def read(root, period, now):
    base = directory(root).resolve()
    primary = base / 'CURRENT_FINANCE_SNAPSHOT_V1.json'
    paths = [primary, *sorted(base.glob('????-??-??/W06_FINANCE_SNAPSHOT_*.json'), reverse=True)]
    candidates = []
    invalid_matching = False
    for path in paths:
        if not path.is_file():
            continue
        try:
            if not path.resolve().is_relative_to(base) or path.stat().st_size > 2_000_000:
                raise ValueError('UNSAFE_SNAPSHOT_FILE')
            doc = json.loads(path.read_text(encoding='utf-8-sig'))
            p = doc.get('period', {})
            if p.get('preset') != PRESETS[period['id']]:
                continue
            if (p['from'], p['to']) != (period['from'], period['to']):
                # A rolling preset from yesterday must not become today's result.
                if path == primary:
                    candidates.append((doc, path, 'PERIOD_EXPIRED'))
                continue
            doc = normalize_legacy_safe_missing(doc)
            validate(doc, now)
            candidates.append((doc, path, None))
        except (OSError, ValueError, KeyError, TypeError, OverflowError, AttributeError):
            if path == primary:
                return empty(period, now, 'INVALID'), {'status': 'INVALID', 'path': None, 'message': MESSAGES['INVALID']}
            invalid_matching = True
            continue
    matching = [c for c in candidates if c[2] is None]
    if not matching:
        state = 'INVALID' if invalid_matching else 'STALE' if candidates else 'MISSING'
        return empty(period, now, state), {'status': state, 'path': None, 'message': MESSAGES[state]}
    doc, path, _ = max(matching, key=lambda c: instant(c[0]['generated_at']))
    fresh = doc['freshness']
    state = fresh['status']
    if state == 'FRESH' and instant(fresh['valid_until']) <= now:
        state = 'STALE'
    if state == 'NO_DATA':
        state = 'INSUFFICIENT_DATA'
    message = MESSAGES.get(state, MESSAGES['INSUFFICIENT_DATA'] if doc['source_status'] == 'INSUFFICIENT_DATA' else '')
    return copy.deepcopy(doc), {'status': state, 'path': path.relative_to(Path(root).resolve()).as_posix(), 'message': message}


def publish(root, snapshot, now, *, current=True, filename=None):
    """Explicit local W06 output operation, never called by HTTP readers."""
    audit_result = audit(snapshot, now)
    allowed_audits = {'PASS', 'PARTIAL_VALID', 'SEMANTIC_SOURCE_DIFFERENCE'}
    if audit_result['audit_result'] not in allowed_audits:
        raise ValueError(audit_result.get('blocker') or audit_result['audit_result'])
    if current and snapshot['period']['preset'] == 'AUGUST_2026':
        raise ValueError('HISTORICAL_CANNOT_REPLACE_CURRENT')
    base = directory(root)
    at = instant(snapshot['generated_at']).astimezone(timezone.utc)
    name = filename or ('W06_FINANCE_SNAPSHOT_' + at.strftime('%Y%m%dT%H%M%S%fZ') + '_' + snapshot['period']['preset'] + '.json')
    if Path(name).name != name or not name.startswith('W06_FINANCE_SNAPSHOT_') or not name.endswith('.json'):
        raise ValueError('INVALID_SNAPSHOT_FILENAME')
    dated = base / at.date().isoformat() / name
    dated.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    # Immutable dated evidence. Repeating the identical publication is idempotent.
    if dated.exists() and dated.read_text(encoding='utf-8') != content:
        raise ValueError('DATED_SNAPSHOT_CONFLICT')
    if not dated.exists():
        with dated.open('x', encoding='utf-8') as out:
            out.write(content)
    target = base / 'CURRENT_FINANCE_SNAPSHOT_V1.json' if current else dated
    if current:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=base, suffix='.tmp', delete=False) as out:
            out.write(content)
            temp = out.name
        os.replace(temp, target)
    return target


def api_snapshot(doc, load, period):
    """Compatibility aliases are copies of W06 values; no economics arithmetic."""
    result = copy.deepcopy(doc)
    # Writers may emit SKU in any order; UI rows must follow identity, never position.
    result['skus'].sort(key=lambda s: list(IDENTITIES).index(s['efa_sku']))
    state = load['status']
    for entity in [result['portfolio'], *result['skus']]:
        entity.update(mode=doc['financial_mode'], source=load['path'],
                      period_start=period['from'], period_end=period['to'],
                      settlement_status=doc['settlement_status'], freshness=state,
                      data_freshness=state, warnings=doc['warnings'])
        entity.setdefault('complete_costs', False)
        entity.setdefault('delivered_revenue', None)
        entity.setdefault('returns_adjustment', None)
        if 'efa_sku' in entity:
            entity['sku'] = 'UF' + entity['efa_sku'][3:6]
    result['schema_version'] = 'efa_finance_snapshot_v1'
    comparison_classes = {item['classification'] for item in doc.get('source_comparisons', [])}
    audit_result = ('TRUE_DATA_CONFLICT' if 'TRUE_DATA_CONFLICT' in comparison_classes
                    else 'PARTIAL_VALID' if doc['source_status'] == 'PARTIAL'
                    else 'SEMANTIC_SOURCE_DIFFERENCE' if comparison_classes else 'PASS')
    result['metadata'] = {'preset': doc['period']['preset'], 'period_start': period['from'],
        'period_end': period['to'], 'timezone': 'Europe/Moscow', 'generated_at': doc['generated_at'],
        'transport': 'W06_STRUCTURED_SNAPSHOT', 'provider': 'W06', 'load_status': state,
        'message': load['message'], 'snapshot_path': load['path'],
        'historical_reference': doc['period']['preset'] == 'AUGUST_2026',
        'source_health': {'finance': {'status': state, 'observed_at': doc['freshness']['observed_at']}},
        'period_finance_available': doc['source_status'] != 'INSUFFICIENT_DATA',
        'audit_result': audit_result,
        'profit_available': doc['portfolio']['profit_rub'] is not None}
    result['provider_check'] = {'owner': 'W06', 'status': state,
        'refresh_required': state in {'MISSING', 'STALE', 'UNKNOWN', 'INVALID', 'INSUFFICIENT_DATA'},
        'finance_blocker': doc['settlement_status'] == 'INSUFFICIENT_SETTLEMENT_DATA',
        'message': load['message']}
    return result


def attach(finance, now, root):
    from finance_model import blank, metric
    mapping = {'commission': 'ozon_commission', 'advertising': 'advertising_total',
               'contribution': 'contribution_rub', 'margin': 'contribution_pct',
               'settlement_profit': 'profit_rub'}
    finance['snapshots'] = {}
    finance['sources'] = []
    finance['data_gaps'] = []
    for p in finance['periods']:
        doc, load = read(root, p, now)
        snap = api_snapshot(doc, load, p)
        finance['snapshots'][PRESETS[p['id']]] = snap
        view = blank(p)
        for target, entity in zip([view['portfolio'], *(s['metrics'] for s in view['skus'])],
                                  [snap['portfolio'], *snap['skus']]):
            for key in target:
                field = mapping.get(key, key)
                meta = entity.get('field_metadata', {}).get(field, {})
                target[key] = metric(entity.get(field), p, source=meta.get('source', load['path']),
                    mode=meta.get('financial_mode', doc['financial_mode']),
                    observed_at=meta.get('source_timestamp', doc['freshness']['observed_at']),
                    scope=meta.get('scope', 'Канонический результат W06; без пересчёта в Control Center.'),
                    settlement_status=doc['settlement_status'],
                    cohort=meta.get('cohort_basis', meta.get('date_basis', 'accrual_date')))
                target[key]['freshness'] = load['status']
                target[key]['missing_reason'] = meta.get('missing_reason')
            # Optional W06 presentation fields are already reported, not derived here.
            for key, datum in entity.get('presentation_metrics', {}).items():
                if key in target and key not in {'profit_before_tax', 'settlement_profit'}:
                    target[key] = {**copy.deepcopy(datum), 'freshness': load['status']}
        view.update(available=any(v['value'] is not None for v in view['portfolio'].values()),
                    sources=[load['path']] if load['path'] else [],
                    data_gaps=list(dict.fromkeys(([load['message']] if load['message'] else []) + doc['warnings'])),
                    current_snapshot_metadata=snap['metadata'], current_snapshot_warnings=doc['warnings'])
        inverse = {v: k for k, v in mapping.items()}
        view['reconciliation'] = [{'metric': inverse.get(r['field'], r['field']),
            'portfolio': r['portfolio'], 'sku_sum': r['sku_sum'], 'difference': r['gap'],
            'status': r['status']} for r in doc['reconciliation']['fields']]
        if 'presentation_bridge' in doc['reconciliation']:
            view['bridge'] = copy.deepcopy(doc['reconciliation']['presentation_bridge'])
        finance['views'][p['id']] = view
        finance['sources'].extend(view['sources'])
    finance['default_period'] = 'this_month'
    return finance


def build(root, now):
    from finance_model import period_options
    return attach({'schema_version': 'efa.control_center.finance.v3',
                   'periods': period_options(now), 'views': {}}, now, root)
