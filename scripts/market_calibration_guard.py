"""Offline dated-reference context, never automated selection or legal verification."""
import csv
import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'references/market-calibration-v01'
SALARY = 'Salary_Calibration_Matrix_v0.1.csv'


def load_salary():
    with (DATA / SALARY).open(encoding='utf-8', newline='') as stream:
        return [dict(row, reference_id=f'{SALARY}:row-{i}', last_verified=None)
                for i, row in enumerate(csv.DictReader(stream), 2)]


def import_errors():
    manifest = json.loads((DATA / 'manifest.json').read_text())
    return [e['file'] for e in manifest['artifacts']
            if hashlib.sha256((DATA / e['file']).read_bytes()).hexdigest() != e['sha256']]


def freshness(captured_date, as_of, category, review=None):
    try:
        captured, today = date.fromisoformat(captured_date), date.fromisoformat(as_of)
        if captured > today:
            return 'RECHECK_REQUIRED'
    except (TypeError, ValueError):
        return 'RECHECK_REQUIRED'
    if category == 'VOLATILE':
        return 'ROLE_LEVEL_FRESH_VERIFY'
    if category == 'METHOD':
        return 'DURABLE_UNLESS_POLICY_CHANGE'
    review = review or {}
    if (review.get('as_of') != as_of or not review.get('reason')
            or review.get('captured_date') != captured_date):
        return 'RECHECK_REQUIRED'
    return ('DATED_CONTEXT_ONLY' if review.get('decision') == 'USABLE_FOR_CYCLE'
            else 'STALE_RECHECK_REQUIRED')


def compare_base(job, row, as_of, review=None):
    """Only a reviewed fixed-base comparison to a matched dated common interval."""
    result = {'market_quality_band': 'INSUFFICIENT_REFERENCE_DATA',
              'reference_id': row.get('reference_id'),
              'confidence': row.get('confidence', 'UNKNOWN'),
              'traceability_status': row.get('traceability_status', 'UNKNOWN'),
              'captured_date': row.get('captured_date'), 'last_verified': row.get('last_verified'),
              'source_refs': row.get('source_refs'), 'derivation_type': row.get('derivation_type'),
              'limitations': row.get('important_limitations'),
              'freshness': freshness(row.get('captured_date'), as_of, 'SALARY', review),
              'actual_base': job.get('base'), 'actual_source_refs': job.get('refs'),
              'automatic_action': None, 'percentile': None, 'candidate_evidence': False,
              'eligibility': job.get('eligibility', 'VERIFY'),
              'quality_concerns': list(job.get('quality_concerns', [])),
              'reference_use': 'DIRECTIONAL_ONLY', 'reason': 'scope, source or pay basis unresolved'}
    if result['freshness'] != 'DATED_CONTEXT_ONLY':
        result.update(reference_use='HISTORICAL_ONLY', reason='dated reference requires cycle/age review')
        return result
    if not all(job.get(k) == row.get(k) and job.get(k) for k in ('market', 'city', 'route', 'role_family', 'currency_basis')):
        return result
    if (not job.get('refs') or job.get('role_source_reviewed') is not True
            or not job.get('role_key') or job.get('observed_as_of') != as_of):
        return result
    if row.get('traceability_status') not in {'FULL', 'PARTIAL'} or not row.get('source_refs'):
        return result
    if 'Prototyping' in row.get('role_family', ''):
        result['reason'] = 'sparse family; adjacent figures are not an exact benchmark'
        return result
    band = re.fullmatch(r'£?(\d+(?:\.\d+)?)k[–-]£?(\d+(?:\.\d+)?)k', row.get('common_normal_observed', ''))
    base = job.get('base')
    if not band or isinstance(base, bool) or not isinstance(base, (int, float)) or not math.isfinite(base) or base < 0:
        return result
    low, high = (float(v) * 1000 for v in band.groups())
    if low > high:
        return result
    result['market_quality_band'] = ('BELOW_DIRECTIONAL_BAND' if base < low else
                                    'ABOVE_DIRECTIONAL_BAND' if base > high else 'WITHIN_DIRECTIONAL_BAND')
    result['reason'] = 'actual role base compared with dated common interval; no selection threshold'
    return result


def benefits_context():
    with (DATA / 'Benefits_Employment_Conditions_Matrix_v0.1.csv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    return [dict(market=market, city='NOT_SPECIFIED', role_family='NOT_APPLICABLE',
                 dimension=r['dimension'], captured_date=r['captured_date'], last_verified=None,
                 confidence='UNKNOWN_NOT_SUPPLIED', traceability_status='NOT_ASSESSED',
                 source_refs=r['authority_or_evidence'], derivation_type='RETAINED_MARKET_CONTEXT',
                 limitations='Source labels are not a row-level trace audit; verify actual terms and current rights',
                 baseline=r[market+'_market_baseline'], competitive=r[market+'_competitive_signal'],
                 verify=r[market+'_role_level_verify'], volatility=r['volatility'])
            for r in rows for market in ('China', 'UK')]
