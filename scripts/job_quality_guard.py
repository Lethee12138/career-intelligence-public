"""Pure review of explicitly grounded quality signals; no salary market model.

Signal classification, source reliability and living-floor context are reviewed
inputs, not inferred from title, brand, salary amount or prose. No offer ranking,
weighted scores, source I/O, legal determination or preparation-gate replacement.
"""
import re
from guard import RECOMMENDATIONS

TOPICS = ('Compensation', 'Total Compensation', 'Workload/Rest', 'Annual Leave',
          'Team/Manager Environment', 'Stability/Risk', 'Growth/Ownership',
          'Career Capital', 'Work Interest', 'Commute/Work Arrangement', 'Travel', 'Probation')
NEGATIVE = {
    'low_pay_context': 'Compensation', 'structural_overtime': 'Workload/Rest',
    'unusable_leave': 'Annual Leave', 'intimidating_management': 'Team/Manager Environment',
    'payroll_risk': 'Stability/Risk', 'extreme_instability': 'Stability/Risk',
    'mechanical_low_value_work': 'Work Interest', 'very_long_daily_commute': 'Commute/Work Arrangement',
    'long_probation_with_elimination_risk': 'Probation',
}
PREFERRED = {'predictable_rest': 'Workload/Rest', 'usable_generous_leave': 'Annual Leave',
             'clear_support_growing_autonomy': 'Team/Manager Environment',
             'meaningful_ownership': 'Growth/Ownership', 'credible_mobility': 'Career Capital',
             'interesting_work': 'Work Interest', 'strong_contextual_pay': 'Compensation'}
BONUS = {'hybrid': 'Commute/Work Arrangement', 'obtainable_housing_support': 'Total Compensation',
         'housing_fund': 'Total Compensation', 'extra_festival_rest': 'Annual Leave',
         'contingent_bonus': 'Total Compensation', 'other_benefits': 'Total Compensation'}
TRADEABLE = {'exceptional_compensated_overtime': 'Workload/Rest',
            'moderate_business_risk': 'Stability/Risk', 'normal_probation_80_percent': 'Probation',
            'occasional_travel': 'Travel', 'full_office': 'Commute/Work Arrangement'}


def grounded(o):
    return (o.get('reviewed') is True and bool(o.get('refs'))
            and o.get('source_scope') in {'SYNTHETIC', 'SCOPED_EVIDENCE'}
            and bool(o.get('rationale')) and o.get('rationale') != 'UNKNOWN')


def quality_review(offer):
    result = {'job_quality_fit': 'UNKNOWN', 'concerns': [], 'positives': [], 'tradeable': [],
              'performance_environment_risks': [], 'verify_items': [],
              'unknown_topics': list(TOPICS), 'recommendation_effect': 'UNCHANGED',
              'capability_fit': offer.get('capability_fit', 'UNKNOWN'),
              'recommendation': offer.get('base_recommendation', 'Explore')}
    if result['recommendation'] not in RECOMMENDATIONS:
        raise ValueError('Use the accepted recommendation vocabulary')
    hard_floor = False
    for o in offer.get('observations', []):
        signal = o.get('signal')
        if not grounded(o):
            result['verify_items'].append(signal or 'unresolved observation')
            continue
        group, strength = None, None
        if signal == 'below_confirmed_living_floor':
            context = o.get('floor_context', {})
            if context.get('human_confirmed') is not True or not all(context.get(k) and context[k] != 'UNKNOWN'
                for k in ('city', 'role_family', 'budget_basis', 'personal_floor_ref')):
                result['verify_items'].append('living floor is not a contextual confirmed hard floor')
                continue
            topic, group, strength = 'Compensation', 'concerns', 'HARD_FLOOR'
            hard_floor = True
        elif signal in NEGATIVE:
            topic, group, strength = NEGATIVE[signal], 'concerns', 'STRONG_NEGATIVE'
        elif signal in PREFERRED:
            topic, group, strength = PREFERRED[signal], 'positives', 'STRONG_PREFERENCE'
        elif signal in BONUS:
            topic, group, strength = BONUS[signal], 'positives', 'POSITIVE_BONUS'
        elif signal in TRADEABLE:
            topic, group, strength = TRADEABLE[signal], 'tradeable', 'TRADEABLE'
        elif signal == 'known_context':
            topic = o.get('topic')
            if topic not in TOPICS:
                result['verify_items'].append('unrecognized context topic')
                continue
        else:
            result['verify_items'].append(signal or 'unrecognized signal')
            continue
        if topic in result['unknown_topics']:
            result['unknown_topics'].remove(topic)
        if group:
            result[group].append({'signal': signal, 'topic': topic, 'strength': strength,
                                  'refs': o['refs'], 'rationale': o['rationale']})
        if signal == 'intimidating_management':
            result['performance_environment_risks'].append('PERFORMANCE_ENVIRONMENT_RISK')
    # No counting or cancellation of concerns by benefits. Positive-only coverage
    # remains MIXED: unknown topics never turn into a complete quality endorsement.
    if result['concerns']:
        result['job_quality_fit'] = 'LOW'
        if hard_floor:
            result['recommendation'] = 'Not Viable Currently'
            result['recommendation_effect'] = 'CONTEXTUAL_HARD_FLOOR'
        elif result['recommendation'] != 'Not Viable Currently':
            result['recommendation'] = 'Low Priority'
            result['recommendation_effect'] = 'MATERIAL_DOWNGRADE; retain any existing eligibility/source restrictions'
    elif len(result['unknown_topics']) < len(TOPICS):
        result['job_quality_fit'] = 'MIXED'
    return result


def hardship_review(proposal):
    """A complete exchange can be reviewed; it never automatically restores rank."""
    required = ('cost', 'duration', 'specific_return', 'return_refs', 'mitigation', 'review_or_exit_condition')
    complete = all(proposal.get(k) and proposal[k] != 'UNKNOWN' for k in required)
    if not complete or proposal.get('return_credible_reviewed') is not True or proposal.get('cost_bounded_reviewed') is not True:
        return 'INSUFFICIENT_JUSTIFICATION'
    return 'HUMAN_TRADEOFF_REVIEW; NO_AUTOMATIC_PRIORITY_RESTORATION'


def pay_basis_errors(components):
    """Validate component basis (three-letter currency syntax), not market value or cross-market comparability."""
    errors = []
    for c in components:
        if c.get('included_in_guaranteed') is True:
            if c.get('guaranteed') is not True or c.get('obtainable') is not True or not c.get('refs'):
                errors.append('uncertain component cannot enter guaranteed comparison')
            if not re.fullmatch(r'[A-Z]{3}', str(c.get('currency', ''))) or c.get('period') not in {'MONTH', 'YEAR'} or c.get('gross_net') not in {'GROSS', 'NET'}:
                errors.append('comparison basis unresolved')
    return errors
