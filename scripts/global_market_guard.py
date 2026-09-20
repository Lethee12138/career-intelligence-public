"""Pure role-scoped market checks on reviewed inputs, not immigration advice.

No legal research, source verification, market estimates, capability mutation,
country exclusion, financial calculator or replacement of existing live gates.
"""
from guard import iso, qualification


TERRITORY_FIELDS = ('current_residence', 'required_work_territory',
                    'residence_requirement', 'overseas_remote_allowed',
                    'relocation_before_start',
                    'work_right_at_required_location_and_start_date')
TERRITORY_STATUSES = {
    'current_residence': {'UK', 'OUTSIDE_UK', 'UNKNOWN'},
    'required_work_territory': {'UK_ONLY', 'SPECIFIC_COUNTRY', 'SPECIFIC_REGION',
                                'GLOBAL_REMOTE', 'UNKNOWN'},
    'residence_requirement': {'MUST_BE_UK_BASED_AT_APPLICATION',
                              'MUST_BE_UK_BASED_BY_START_DATE',
                              'MUST_REMAIN_UK_BASED_DURING_EMPLOYMENT',
                              'NO_SPECIFIC_RESIDENCE_REQUIREMENT', 'UNKNOWN'},
    'overseas_remote_allowed': {'YES', 'NO', 'UNKNOWN'},
    'relocation_before_start': {'CONFIRMED_POSSIBLE', 'CONFIRMED_NOT_POSSIBLE',
                                'CANDIDATE_DECISION_REQUIRED', 'UNKNOWN'},
    'work_right_at_required_location_and_start_date': {'PASS', 'VERIFY', 'FAIL'},
}


def bound(record, job, as_of):
    day = iso(as_of)
    return (bool(job.get('role_key')) and job.get('role_key') != 'UNKNOWN'
            and bool(job.get('employment_market')) and job.get('employment_market') != 'UNKNOWN'
            and record.get('role_key') == job.get('role_key')
            and record.get('market') == job.get('employment_market')
            and record.get('reviewed') is True and bool(record.get('refs'))
            and record.get('applicable_as_of') == as_of and day is not None)


def _signal(job, field, as_of):
    """Return a reviewed territory signal without treating absence as a fact."""
    record = job.get(field)
    if not isinstance(record, dict):
        return 'UNKNOWN', False, {}
    if not bound(record, job, as_of):
        return 'UNKNOWN', True, record
    value = record.get('status')
    if value not in TERRITORY_STATUSES[field]:
        value = 'UNKNOWN'
    return value, True, record


def territory_review(job, as_of, current_work_right='UNKNOWN'):
    """Review role territory/residence separately from immigration sponsorship.

    No explicit territory records means NOT_ASSESSED for backward compatibility.
    A reviewed but unknown material signal remains VERIFY; remote wording alone
    never supplies GLOBAL_REMOTE.
    """
    is_uk = job.get('employment_market') == 'UK'
    values, records, material = {}, {}, False
    for field in TERRITORY_FIELDS:
        value, present, record = _signal(job, field, as_of)
        values[field] = value
        records[field] = record
        material = material or present
    base = {
        **values,
        'territory_gate': 'ELIGIBLE',
        'territory_status': 'NOT_ASSESSED',
        'territory_risks': [],
        'territory_readiness': 'NOT_ASSESSED',
        'territory_material': material,
    }
    if not is_uk or not material:
        return base

    territory = values['required_work_territory']
    residence = values['residence_requirement']
    overseas = values['overseas_remote_allowed']
    current_residence = values['current_residence']
    relocation = values['relocation_before_start']
    reported_location_right = values['work_right_at_required_location_and_start_date']
    risks = []
    reasons = []
    target_country = records['required_work_territory'].get('country', 'UK')
    residence_country = records['current_residence'].get('country', 'UNKNOWN')

    # Explicit global permission is the only way to clear a cross-border remote
    # requirement. A bare Remote/Home Based label never reaches this branch.
    if territory == 'GLOBAL_REMOTE' and overseas == 'YES':
        base['territory_status'] = 'PASS'
        base['territory_readiness'] = 'GLOBAL_REMOTE_ALLOWED'
        base['work_right_at_required_location_and_start_date'] = (
            reported_location_right if reported_location_right != 'UNKNOWN'
            else 'PASS' if current_work_right == 'PASS' else current_work_right)
        return base

    if (territory == 'NO_SPECIFIC_RESIDENCE_REQUIREMENT'
            or residence == 'NO_SPECIFIC_RESIDENCE_REQUIREMENT'):
        if overseas == 'YES':
            base['territory_status'] = 'PASS'
            base['territory_readiness'] = 'GLOBAL_REMOTE_ALLOWED'
            base['work_right_at_required_location_and_start_date'] = (
                reported_location_right if reported_location_right != 'UNKNOWN'
                else 'PASS' if current_work_right == 'PASS' else current_work_right)
            return base

    # A specific territory without a precise residence/remote rule is material
    # uncertainty. Keep it visible instead of treating a title or arrangement
    # label as a global location permission.
    if 'UNKNOWN' in {territory, residence, overseas, current_residence}:
        risks.append('WORK_TERRITORY_OR_RESIDENCE_VERIFY')
        reasons.append('required work territory, residence or overseas remote scope unresolved')
        base.update(territory_gate='VERIFY', territory_status='VERIFY',
                    territory_risks=risks, territory_readiness='WORK_TERRITORY_VERIFY',
                    reasons=reasons)
        return base

    required_uk = territory == 'UK_ONLY' or target_country == 'UK'
    if not required_uk:
        # This framework does not invent a foreign-country residence rule from
        # a generic market label; retain the reviewed work-right result.
        base['territory_status'] = 'PASS' if current_residence != 'UNKNOWN' else 'VERIFY'
        base['territory_gate'] = 'ELIGIBLE' if base['territory_status'] == 'PASS' else 'VERIFY'
        base['territory_readiness'] = 'STANDARD_REVIEW' if base['territory_gate'] == 'ELIGIBLE' else 'WORK_TERRITORY_VERIFY'
        return base

    if overseas == 'YES' and territory == 'UK_ONLY':
        risks.append('CONFLICTING_TERRITORY_REMOTE_ASSERTIONS')
        reasons.append('UK-only territory conflicts with an overseas-remote permission')
        base.update(territory_gate='VERIFY', territory_status='VERIFY',
                    territory_risks=risks, territory_readiness='WORK_TERRITORY_VERIFY',
                    reasons=reasons)
        return base

    at_application = residence == 'MUST_BE_UK_BASED_AT_APPLICATION'
    at_start = residence == 'MUST_BE_UK_BASED_BY_START_DATE'
    during_role = residence == 'MUST_REMAIN_UK_BASED_DURING_EMPLOYMENT'
    already_in_uk = current_residence == 'UK' or residence_country == 'UK'

    if already_in_uk:
        location_right = 'PASS' if current_work_right == 'PASS' else current_work_right
    elif relocation == 'CONFIRMED_POSSIBLE':
        location_right = 'PASS' if current_work_right == 'PASS' else current_work_right
    elif relocation == 'CONFIRMED_NOT_POSSIBLE':
        location_right = 'FAIL'
    else:
        location_right = 'VERIFY'
    base['work_right_at_required_location_and_start_date'] = (
        reported_location_right if reported_location_right != 'UNKNOWN' else location_right)
    location_right = base['work_right_at_required_location_and_start_date']

    if location_right == 'FAIL' and (at_application or at_start or during_role):
        risks.append('REQUIRED_UK_RESIDENCE_NOT_VIABLE_CURRENTLY')
        reasons.append('candidate cannot satisfy the required UK residence/territory condition')
        base.update(territory_gate='NOT ELIGIBLE', territory_status='NOT_VIABLE_CURRENTLY',
                    territory_risks=risks, territory_readiness='NOT_VIABLE_CURRENTLY',
                    reasons=reasons)
    elif (location_right == 'PASS' and not already_in_uk
          and relocation == 'CONFIRMED_POSSIBLE'
          and (at_application or at_start or during_role)):
        risks.append('RELOCATION_OR_START_LOCATION_VERIFY')
        reasons.append('relocation is possible but required UK residence at the applicable time is not yet confirmed')
        base.update(territory_gate='VERIFY', territory_status='VERIFY',
                    territory_risks=risks, territory_readiness='RELOCATION_OR_START_LOCATION_VERIFY',
                    reasons=reasons)
    elif location_right != 'PASS':
        risks.append('RELOCATION_OR_START_LOCATION_VERIFY')
        reasons.append('UK residence/territory feasibility needs relocation or start-location verification')
        base.update(territory_gate='VERIFY', territory_status='VERIFY',
                    territory_risks=risks, territory_readiness='RELOCATION_OR_START_LOCATION_VERIFY',
                    reasons=reasons)
    else:
        base['territory_status'] = 'PASS'
        base['territory_readiness'] = 'STANDARD_REVIEW'
    return base


def authorization_review(job, as_of):
    c, s, other = (job.get(k, {}) for k in ('candidate_authorization', 'employer_sponsorship', 'other_route'))
    permanent = job.get('permanent_unrestricted_right_requirement', {})
    no_sponsorship = job.get('explicit_no_sponsorship', {})
    need, state, gate = 'UNKNOWN', 'SPONSORSHIP_VERIFY', 'VERIFY'
    reasons = []
    is_uk = job.get('employment_market') == 'UK'
    candidate_known = bound(c, job, as_of)
    sponsor_known = bound(s, job, as_of) and s.get('authority_for_job') is True
    permanent_known = bound(permanent, job, as_of)
    no_sponsorship_known = bound(no_sponsorship, job, as_of)
    current_right = ('PASS' if candidate_known and c.get('status') == 'ALREADY_AUTHORISED'
                     and c.get('valid_for_role') is True else
                     'FAIL' if candidate_known and c.get('status') == 'NO_CURRENT_RIGHT' else 'UNKNOWN')
    permanent_status = permanent.get('status') if permanent_known and permanent.get('status') in {'YES', 'NO'} else 'UNKNOWN'
    explicit_no = no_sponsorship.get('status') if no_sponsorship_known and no_sponsorship.get('status') in {'YES', 'NO'} else (
        'YES' if sponsor_known and s.get('status') == 'DOES_NOT' else
        'NO' if sponsor_known and s.get('status') == 'OFFERS' else 'UNKNOWN')
    future_need = (c.get('future_sponsorship_need') if candidate_known
                   and c.get('future_sponsorship_need') in {'REQUIRED', 'NOT_REQUIRED', 'UNKNOWN'} else 'UNKNOWN')
    employer_capability = ('CONFIRMED' if bound(s, job, as_of) and s.get('sponsor_capability') == 'CONFIRMED'
                           else 'NOT_CONFIRMED' if bound(s, job, as_of) and s.get('sponsor_capability') == 'NOT_CONFIRMED'
                           else 'UNKNOWN')
    exact_role_sponsorship = ('CONFIRMED' if sponsor_known and s.get('status') == 'OFFERS' else
                              'NOT_OFFERED' if sponsor_known and s.get('status') == 'DOES_NOT' else 'UNKNOWN')
    risks = []
    if candidate_known and c.get('status') == 'ALREADY_AUTHORISED':
        if c.get('valid_for_role') is True:
            state, gate = 'ALREADY_AUTHORISED', 'ELIGIBLE'
            need = 'NOT_REQUIRED'
            if is_uk and permanent_status == 'YES' and c.get('permanent_unrestricted_right') is not True:
                risks.append('PERMANENT_UNRESTRICTED_RIGHT_REQUIREMENT')
                if permanent.get('applies_at') in {'APPLICATION', 'START_DATE'}:
                    gate = 'NOT ELIGIBLE'
                    reasons.append('permanent unrestricted right is an applicable hard requirement')
                else:
                    gate = 'VERIFY'
                    reasons.append('permanent-right requirement timing or candidate status unresolved')
            if is_uk and future_need == 'UNKNOWN':
                risks.extend(['LONG_TERM_IMMIGRATION_RISK', 'FUTURE_SPONSORSHIP_VERIFY'])
            elif is_uk and future_need == 'REQUIRED':
                risks.append('LONG_TERM_IMMIGRATION_RISK')
                if explicit_no == 'YES':
                    risks.append('LONG_TERM_ELIGIBILITY_RISK')
                    if c.get('future_need_within_role') is True:
                        gate = 'NOT ELIGIBLE'
                        reasons.append('future continuing right is required during the role and exact role excludes sponsorship')
                    else:
                        gate = 'VERIFY'
                        reasons.append('future sponsorship required and exact no-sponsorship condition needs timing review')
        else:
            reasons.append('authorization restrictions/applicability unresolved')
    elif candidate_known and c.get('status') == 'NO_CURRENT_RIGHT':
        need = 'SPONSORSHIP_REQUIRED'
        if sponsor_known and s.get('status') == 'OFFERS':
            state = 'SPONSORSHIP_AVAILABLE'
            if s.get('candidate_route_conditions_verified') is True:
                gate = 'ELIGIBLE'
            else:
                reasons.append('employer support is not candidate route eligibility')
        elif bound(other, job, as_of) and other.get('status') == 'POSSIBLE_UNVERIFIED':
            state = 'OTHER_ROUTE_VERIFY'
            reasons.append('alternative route requires verification')
        elif sponsor_known and s.get('status') == 'DOES_NOT':
            if bound(other, job, as_of) and other.get('status') == 'NO_OTHER_ROUTE':
                state, gate = 'SPONSORSHIP_UNAVAILABLE', 'NOT ELIGIBLE'
                reasons.append('exact job excludes sponsorship; no applicable candidate route')
            else:
                reasons.append('no sponsorship; other candidate routes unresolved')
        else:
            reasons.append('job-specific sponsorship unresolved')
    else:
        reasons.append('candidate current work rights unresolved')
    territory = territory_review(job, as_of, current_right)
    reasons.extend(territory.get('reasons', []))
    other_gate = qualification(job.get('qualification_checks', []), job.get('qualification_coverage_complete') is True)
    territory_gate = territory['territory_gate']
    overall = ('NOT ELIGIBLE' if 'NOT ELIGIBLE' in (gate, other_gate, territory_gate)
               else 'ELIGIBLE' if gate == other_gate == territory_gate == 'ELIGIBLE' else 'VERIFY')
    risks.extend(territory.get('territory_risks', []))
    routing_readiness = ('WATCH_VERIFY_CURRENT_WORK_RIGHT' if current_right == 'UNKNOWN' else
                         'NOT_VIABLE_CURRENTLY' if territory_gate == 'NOT ELIGIBLE' else
                         territory['territory_readiness'] if territory_gate == 'VERIFY' else
                         'NOT_ELIGIBLE_PERMANENT_RIGHT_REQUIREMENT' if gate == 'NOT ELIGIBLE' and permanent_status == 'YES' else
                         'NOT_ELIGIBLE_FUTURE_CONTINUING_RIGHT' if gate == 'NOT ELIGIBLE' and 'LONG_TERM_ELIGIBILITY_RISK' in risks else
                         'LONG_TERM_ELIGIBILITY_RISK' if is_uk and gate == 'VERIFY' and current_right == 'PASS' else
                         'CURRENT_RIGHT_PASS_FUTURE_VERIFY' if is_uk and current_right == 'PASS' and future_need == 'UNKNOWN' else
                         'ROLE_SPONSORSHIP_CONFIRMED' if exact_role_sponsorship == 'CONFIRMED' else 'STANDARD_REVIEW')
    return {'sponsorship_need': need, 'resolution_state': state, 'work_right_gate': gate,
            'other_qualification': other_gate, 'qualification': overall, 'reasons': reasons,
            'territory_gate': territory_gate,
            'territory_status': territory.get('territory_status', 'NOT_ASSESSED'),
            'territory_reasons': territory.get('reasons', []),
            'territory_risks': territory.get('territory_risks', []),
            'territory_readiness': territory.get('territory_readiness', 'NOT_ASSESSED'),
            'territory_material': territory.get('territory_material', False),
            'current_residence': territory.get('current_residence', 'UNKNOWN'),
            'required_work_territory': territory.get('required_work_territory', 'UNKNOWN'),
            'residence_requirement': territory.get('residence_requirement', 'UNKNOWN'),
            'overseas_remote_allowed': territory.get('overseas_remote_allowed', 'UNKNOWN'),
            'relocation_before_start': territory.get('relocation_before_start', 'UNKNOWN'),
            'work_right_at_required_location_and_start_date': territory.get(
                'work_right_at_required_location_and_start_date', 'UNKNOWN'),
            'current_work_right': current_right,
            'permanent_unrestricted_right_requirement': permanent_status,
            'explicit_no_sponsorship': explicit_no,
            'future_sponsorship_need': future_need,
            'employer_sponsor_capability': employer_capability,
            'exact_role_sponsorship': exact_role_sponsorship,
            'risk_flags': sorted(set(risks)), 'routing_readiness': routing_readiness,
            'role_key': job.get('role_key', 'UNKNOWN'), 'scope': 'THIS_JOB_ONLY',
            'visa_issued': 'NOT_ASSERTED', 'capability_effect': 'NONE', 'market_exclusion': False}


def strategy_scope(review, worthwhile):
    if review['qualification'] == 'NOT ELIGIBLE':
        return 'STOP_FULL_MATERIALS'
    if review['qualification'] == 'VERIFY':
        return 'STRATEGY_ONLY; WORK_RIGHT_OR_QUALIFICATION_OPEN' if worthwhile else 'VERIFY_BEFORE_FURTHER_EFFORT'
    return 'NORMAL_CORE_GATES_REQUIRED'


def market_identity_errors(job):
    errors = []
    market = job.get('employment_market')
    country = job.get('work_location', {}).get('country')
    if not market or market == 'UNKNOWN':
        errors.append('employment jurisdiction unresolved')
    if not country or country == 'UNKNOWN':
        errors.append('work country unresolved')
    if market != country and job.get('cross_border_arrangement_reviewed') is not True:
        errors.append('market/location mismatch needs cross-border review')
    return errors


def comparison_errors(comparison):
    errors = []
    if comparison.get('conclusion_basis') in {'NOMINAL_NUMBER', 'FX_ONLY'}:
        errors.append('currency conversion is not an offer-quality conclusion')
    if comparison.get('asserts_financial_winner') is True:
        for field in ('pay_basis', 'taxes', 'living_rent_costs', 'benefits', 'hours',
                      'pension_social_insurance', 'relocation', 'visa_costs_constraints'):
            v = comparison.get('context', {}).get(field, {})
            if not v.get('refs') or v.get('reviewed') is not True or v.get('status') not in {'KNOWN', 'NOT_APPLICABLE'}:
                errors.append('comparison context unresolved: ' + field)
    return errors


def benefits_comparison_errors(a, b, equivalent_asserted=False):
    if not equivalent_asserted:
        return []
    fields = ('contribution', 'eligibility', 'access', 'local_treatment')
    if a.get('market') != b.get('market') and any(
        not x.get('refs') or not all(x.get(f) and x[f] != 'UNKNOWN' for f in fields) for x in (a, b)):
        return ['benefit labels are not equivalent across markets']
    return []


def scoped_city_preferences(preference, market):
    return list(preference.get('cities', [])) if preference.get('market') == market else []
