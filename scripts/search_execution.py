"""Portable search handoff, conservative intake and explainable routing.

Offline, reviewed structured inputs only. No search, source authentication,
NLP matching, persistent application tracker or external actions.
"""
from copy import deepcopy
from hashlib import sha256
import json
from urllib.parse import urlsplit
from guard import iso, resolve_status, qualification, DIMENSIONS
from global_market_guard import authorization_review
from job_quality_guard import quality_review

EXECUTORS = ('CHATGPT_WORK', 'WEB_RESEARCH', 'MANUAL_IMPORT', 'OTHER_SEARCH_EXECUTOR')
MARKETS = [{'market': 'China', 'status': 'ACTIVE / HIGH-ACTIVITY EXECUTION MARKET'},
           {'market': 'UK', 'status': 'ACTIVE'},
           {'market': 'Other', 'status': 'OPEN / OPPORTUNITY-DRIVEN'}]
IDENTITY = ('company', 'role_title', 'employment_market', 'country', 'city', 'company_type', 'recruitment_route')
DETAILS = ('official_published_date', 'deadline', 'jd_ref', 'responsibilities', 'requirements',
           'base_salary', 'guaranteed_cash', 'variable', 'benefits', 'workload_signals',
           'leave', 'hybrid', 'probation', 'stability_signals', 'role_family',
           'industry', 'ai_involvement', 'technical_depth_requirement', 'candidate_zone',
           'matched_role_hypothesis', 'strongest_capability_match', 'strongest_evidence_refs', 'main_gaps')
AI_INVOLVEMENT = {'NONE', 'AI-ENABLED', 'AI-CORE', 'AGENT-CORE'}
TECHNICAL_DEPTH = {'LOW', 'MODERATE', 'HIGH', 'ENGINEERING-CORE'}
CANDIDATE_ZONE = {'CORE_COMFORT', 'ADJACENT_GROWTH', 'STRATEGIC_STRETCH', 'CURRENTLY_TOO_FAR'}


def present(value):
    return value is not None and value != '' and value != 'UNKNOWN' and value != []


def url(value):
    return isinstance(value, str) and urlsplit(value).scheme in {'https', 'http'} and bool(urlsplit(value).netloc)


def make_handoff(discovery, search_id, created_at, pool=None, target_batch_size=30, executor='OTHER_SEARCH_EXECUTOR'):
    if executor not in EXECUTORS or iso(created_at) is None or not present(search_id):
        raise ValueError('Known executor, search_id and ISO date required')
    if type(target_batch_size) is not int or target_batch_size < 1:
        raise ValueError('Positive advisory target required')
    hypotheses = deepcopy(discovery.get('role_hypotheses', []))
    queries = []
    for h in hypotheses:
        # Query vocabulary is a hypothesis, never a job equivalence or demand fact.
        for market in ('China', 'UK', 'Other'):
            terms = h.get('search_terms', {}).get(market, {})
            for axis in ('title', 'responsibility', 'problem', 'output', 'negative'):
                for item in terms.get(axis, []):
                    if item.get('term') and item.get('why'):
                        queries.append({'hypothesis_id': h['id'], 'market': market, 'axis': axis, **item})
    coverage_gaps = [m for m in ('China', 'UK') if not any(q['market'] == m and q['axis'] in {'responsibility', 'problem', 'output'} for q in queries)]
    safe_pool = {k: deepcopy((pool or {}).get(k, 'UNKNOWN')) for k in ('pool_id', 'captured_at', 'company_constraints')}
    safe_pool['entries'] = [{k: deepcopy(e[k]) for k in IDENTITY + ('identity', 'business_unit', 'programme', 'pool_id', 'application_status', 'lane', 'queue_state') if k in e} for e in (pool or {}).get('entries', [])]
    coverage_plan = deepcopy(discovery.get('coverage_plan', {}))
    return {'schema_version': '0.2.3', 'search_id': search_id, 'created_at': created_at,
            'executor': executor, 'market_scope': deepcopy(MARKETS), 'role_hypotheses': hypotheses,
            'location_scope': deepcopy(discovery.get('location_scope', ['China preferred cities', 'UK', 'Other opportunity-driven'])),
            'query_sets': queries, 'query_method': 'Combine title + responsibility/problem/output; negative terms are reviewed traps, not automatic exclusions',
            'source_priorities': ['1 official careers/ATS/campus', '2 official public employment',
                                  '3 job platforms/university careers', '4 community/referral discovery'],
            'authority_verification_rules': ['Resolve exact official job/programme and eligibility/sponsor source',
                'Capture inspected content, exact identity, dates and unresolved conflicts; missing authority remains VERIFY'],
            'candidate_fields_required': list(IDENTITY) + ['candidate_id', 'discovery_source', 'discovery_source_tier',
                'authority_source', 'official_url', 'source_capture_date', 'last_verified', 'opening_status'] + list(DETAILS) + [
                'work_right_review.current_residence', 'work_right_review.required_work_territory',
                'work_right_review.residence_requirement', 'work_right_review.overseas_remote_allowed',
                'work_right_review.relocation_before_start',
                'work_right_review.work_right_at_required_location_and_start_date'],
            'dedupe_rules': ['Scoped official ID', 'Exact official URL', 'Complete official identity tuple',
                             'No fuzzy merge; keep variants and conflicts; compare current pool'],
            'target_batch_size': target_batch_size, 'target_is_advisory': True,
            'discovery_mode': 'HIGH_RECALL', 'selection_mode': 'SEPARATE_DOWNSTREAM_SCREEN',
            'ai_neutral_by_default': True, 'coverage_plan': coverage_plan,
            'coverage_rules': ['Audit role family, industry, company, city/market, AI involvement and source accessibility',
                'Soft coverage targets guide search; they are not market-distribution claims or hard quotas',
                'Two or three strong Targeted candidates do not complete broad discovery'],
            'stop_conditions': ['duplicate-heavy after coverage expansion', 'no new responsibility patterns across relevant capability roots',
                'authority unavailable', 'mostly hard-constraint violations after broad search',
                'coverage plan explored and marginal useful patterns diminished', 'advisory target or agreed search window reached'],
            'human_constraints': deepcopy(discovery.get('human_constraints', [])) + [
                'No submission, login, recruiter contact or invented fields', 'No candidate private evidence upload',
                'Return partial coverage and stop reasons; no fabricated vacancies to meet quota'],
            'existing_pool': safe_pool, 'existing_pool_coverage': 'SUPPLIED' if pool else 'UNKNOWN',
            'input_refs': deepcopy(discovery.get('input_refs', [])),
            'coverage_gaps': coverage_gaps,
            'handoff_state': ('READ_EXISTING_DISCOVERY' if not hypotheses or not queries else
                              'EXPAND_ACTIVE_MARKET_QUERIES' if coverage_gaps else 'READY_FOR_EXECUTOR_REVIEW'),
            'external_action': False}


def coverage_audit(candidates, coverage_targets=None, coverage_reviewed=False):
    """Describe returned-batch concentration; never infer market distribution."""
    def city_market(candidate):
        values = (candidate.get('employment_market'), candidate.get('city'))
        return values if all(present(value) for value in values) else None

    def source_domains(candidate):
        sources = candidate.get('discovery_source', [])
        if isinstance(sources, str):
            sources = [sources]
        domains = tuple(sorted({urlsplit(source).netloc for source in sources if url(source)}))
        return domains or None

    axes = {
        'role_family': lambda c: c.get('role_family'),
        'industry': lambda c: c.get('industry'),
        'company': lambda c: c.get('company'),
        'city_market': city_market,
        'ai_involvement': lambda c: c.get('ai_involvement'),
        'source_accessibility': source_domains,
    }
    biases, distributions = [], {}
    for axis, getter in axes.items():
        values = [getter(c) for c in candidates]
        values = [v for v in values if present(v) and v != ('',)]
        counts = {}
        for value in values:
            key = json.dumps(value, ensure_ascii=False, sort_keys=True)
            counts[key] = counts.get(key, 0) + 1
        distributions[axis] = counts
        if len(values) >= 3 and counts:
            top, count = max(counts.items(), key=lambda item: item[1])
            if count > len(values) / 2:
                biases.append({'axis': axis, 'dominant_value': json.loads(top),
                               'observed_count': count, 'known_count': len(values),
                               'meaning': 'RESULT_SET_CONCENTRATION_ONLY'})
    missing = []
    for axis, expected in (coverage_targets or {}).items():
        if axis not in distributions or not isinstance(expected, list):
            continue
        observed = set(distributions[axis])
        missing.extend({'axis': axis, 'area': item} for item in expected
                       if json.dumps(item, ensure_ascii=False, sort_keys=True) not in observed)
    state = ('COVERAGE_BIAS_DETECTED' if biases else
             'COVERAGE_SUFFICIENT' if coverage_reviewed and not missing else 'COVERAGE_UNREVIEWED')
    return {'coverage_state': state, 'biases': biases, 'missing_relevant_areas': missing,
            'distributions': distributions,
            'interpretation': 'Observed search-result coverage only; not market distribution'}


def identity_keys(record):
    """Identity assertions require scoped official binding; discovery URLs cannot suffice."""
    i = record.get('identity', {})
    if not isinstance(i, dict) or i.get('official_binding_reviewed') is not True or not i.get('refs'):
        return []
    company = record.get('company')
    if not isinstance(company, str) or not present(company):
        return []
    keys = []
    if all(isinstance(i.get(k), str) and present(i[k]) for k in ('official_job_id', 'namespace')):
        keys.append(('ID', company, i['namespace'], i['official_job_id']))
    if url(i.get('official_url')):
        keys.append(('URL', company, i['official_url']))
    fields = ('role_title', 'employment_market', 'city', 'recruitment_route', 'business_unit', 'programme')
    if i.get('complete_tuple_reviewed') is True and all(isinstance(record.get(k), str) and present(record[k]) for k in fields):
        keys.append(('TUPLE', company, *(record[k] for k in fields)))
    return keys


def compatible(a, b):
    ia, ib = a.get('identity', {}), b.get('identity', {})
    if all(present(i.get('official_job_id')) for i in (ia, ib)):
        if (ia.get('namespace'), ia['official_job_id']) != (ib.get('namespace'), ib['official_job_id']):
            return False
    return all(not (present(a.get(k)) and present(b.get(k)) and a[k] != b[k])
               for k in ('company', 'employment_market', 'country', 'city', 'recruitment_route', 'business_unit', 'programme'))


def same_identity(a, b):
    return compatible(a, b) and bool(set(identity_keys(a)) & set(identity_keys(b)))


def review_bound(review, role_key, as_of):
    return (isinstance(review, dict) and review.get('reviewed') is True and review.get('role_key') == role_key
            and review.get('as_of') == as_of and bool(review.get('refs')))


def candidate_context_state(intake):
    """Return a task-local grounding state; never creates a candidate SSOT."""
    context = intake.get('candidate_context')
    candidates = intake.get('candidates', [])
    relevant = [c for c in candidates if c.get('intake_state') != 'CLOSED']
    grounded = []
    for candidate in relevant:
        screen = candidate.get('screen', {})
        dimensions = screen.get('dimensions', {}) if isinstance(screen, dict) else {}
        candidate_fields = all(
            isinstance(dimensions.get(name), dict)
            and present(dimensions[name].get('judgment'))
            for name in ('Evidence Fit', 'Experience Fit', 'Eligibility Fit'))
        if (candidate.get('strongest_evidence_refs') not in ('UNKNOWN', [], None)
                and screen.get('evidence_refs') and candidate_fields):
            grounded.append(candidate)
    surface_grounded = bool(relevant) and len(grounded) * 2 >= len(relevant)
    if isinstance(context, dict):
        safe_context = deepcopy(context)
        if context.get('new_ssot') is not False:
            safe_context['validation_issue'] = 'Candidate context cannot create a new SSOT'
        safe_context['new_ssot'] = False
        valid = (context.get('new_ssot') is False and bool(context.get('provenance'))
                 and iso(context.get('as_of')) is not None and present(context.get('scope'))
                 and bool(context.get('evidence_refs')) and surface_grounded)
        return ('GROUNDED' if valid else 'PRELIMINARY_CONTEXT_REQUIRED'), safe_context
    if surface_grounded:
        refs = sorted({ref for c in grounded for ref in c['screen']['evidence_refs']})
        return 'GROUNDED', {'new_ssot': False, 'provenance': 'EMBEDDED_REVIEWED_SCREEN',
                            'as_of': intake.get('as_of'), 'scope': 'THIS_ROUTING_RUN_ONLY',
                            'evidence_refs': refs}
    return 'PRELIMINARY_CONTEXT_REQUIRED', {'new_ssot': False, 'provenance': 'MISSING_OR_INCOMPLETE',
                                            'as_of': intake.get('as_of'), 'scope': 'THIS_ROUTING_RUN_ONLY',
                                            'evidence_refs': []}


def intake_batch(batch, as_of, mode='HISTORICAL_SNAPSHOT'):
    """Non-destructive groups retain all originals. LIVE is a caller's grounded assertion."""
    if iso(as_of) is None or mode not in {'LIVE', 'HISTORICAL_SNAPSHOT'}:
        raise ValueError('Explicit valid intake date/mode required')
    groups = []
    raw_candidates = batch.get('candidates', [])
    if not isinstance(raw_candidates, list):
        raw_candidates = [{'malformed_batch_candidates': raw_candidates}]
    for raw in raw_candidates:
        item = deepcopy(raw) if isinstance(raw, dict) else {'malformed_raw': raw}
        malformed = []
        for field in IDENTITY + ('role_key',):
            if not isinstance(item.get(field), str):
                item[field] = 'UNKNOWN'
                malformed.append(field)
        for field in ('identity', 'screen', 'qualification_review', 'work_right_review'):
            if not isinstance(item.get(field, {}), dict):
                item[field] = {}
                malformed.append(field)
        if not isinstance(item.get('observations', []), list):
            item['observations'] = []
            malformed.append('observations')
        item['_malformed_fields'] = malformed
        matches = [g for g in groups if any(same_identity(item, v) for v in g)
                   and all(compatible(item, v) for v in g)]
        if len(matches) == 1:
            matches[0].append(item)
        else:
            groups.append([item])
    candidates = []
    for n, variants in enumerate(groups):
        base = variants[0]
        keys = sorted({k for v in variants for k in identity_keys(v)},
                      key=lambda k: ({'ID':0,'URL':1,'TUPLE':2}[k[0]], json.dumps(k)))
        key = json.dumps(keys[0], ensure_ascii=False) if keys else f"UNRESOLVED:{batch.get('batch_id', 'UNKNOWN')}:{n}"
        cid = 'JC-' + sha256(key.encode()).hexdigest()[:12]
        obs = []
        for v in variants:
            for o in v.get('observations', []):
                if isinstance(o, dict):
                    # Executor cannot borrow another role's authority observation.
                    o = deepcopy(o)
                    if o.get('role_key') == v.get('role_key') and present(v.get('role_key')) and identity_keys(v):
                        o['role_key'] = key
                        obs.append(o)
        status = resolve_status(key, obs, as_of, mode)
        fresh = status['live_verified']
        authority_variants = [v for v in variants if any(
            o.get('ref') in status['refs'] and o.get('authority_for_role') is True and o.get('inspected_original') is True
            and o.get('role_key') == v.get('role_key') and (not fresh or o.get('observed_at') == as_of) for o in v.get('observations', []) if isinstance(o, dict))]
        # No mirror overwrite: payload comes from reviewed authoritative variant when available.
        selected = authority_variants[0] if authority_variants else base
        out = {k: deepcopy(selected[k]) if present(selected.get(k)) else 'UNKNOWN' for k in IDENTITY + ('business_unit', 'programme') + DETAILS}
        errors = ['malformed fields VERIFY'] if any(v['_malformed_fields'] for v in variants) else []
        if not keys:
            errors.append('IDENTITY_VERIFY')
        if any(not present(selected.get(k)) for k in IDENTITY):
            errors.append('required identity metadata missing')
        for v in variants:
            if (not url(v.get('discovery_source')) or type(v.get('discovery_source_tier')) is not int or v.get('discovery_source_tier') not in {1, 2, 3, 4}
                    or iso(v.get('source_capture_date')) is None or iso(v['source_capture_date']) > iso(as_of)):
                errors.append('discovery provenance/date VERIFY')
        if out['employment_market'] != out['country'] and selected.get('cross_border_arrangement_reviewed') is not True:
            errors.append('employment market/location VERIFY')
        if not fresh:
            errors.append('current authority VERIFY')
        if len(authority_variants) > 1 and any(
            any(v.get(f) != selected.get(f) for f in ('responsibilities', 'requirements', 'screen', 'qualification_review'))
            for v in authority_variants[1:]):
            errors.append('conflicting authoritative payload VERIFY')
        q = selected.get('qualification_review', {})
        qbound = (fresh and review_bound(q, selected.get('role_key'), as_of)
                  and isinstance(q.get('checks'), list) and all(isinstance(x, dict) for x in q['checks']))
        qstatus = qualification(q.get('checks', []), q.get('coverage_complete') is True) if qbound else 'VERIFY'
        work = selected.get('work_right_review', {})
        wr = authorization_review(work, as_of) if (
            fresh and isinstance(work, dict) and work.get('role_key') == selected.get('role_key')
            and work.get('employment_market') == selected.get('employment_market')
            and all(isinstance(work.get(k), dict) for k in ('candidate_authorization', 'employer_sponsorship', 'other_route'))
            and isinstance(work.get('qualification_checks'), list)
            and all(isinstance(x, dict) for x in work['qualification_checks'])) else {'qualification': 'VERIFY', 'resolution_state': 'SPONSORSHIP_VERIFY'}
        qstatus = ('NOT ELIGIBLE' if 'NOT ELIGIBLE' in (qstatus, wr['qualification']) else
                   'ELIGIBLE' if qstatus == wr['qualification'] == 'ELIGIBLE' else 'VERIFY')
        screen = selected.get('screen', {})
        screen_ok = (review_bound(screen, selected.get('role_key'), as_of)
                     and isinstance(screen.get('dimensions'), dict)
                     and all(isinstance(screen.get(k), list) for k in ('evidence_refs','critical_unknowns','quality_observations')))
        if not isinstance(out['responsibilities'], list) or not out['responsibilities']:
            errors.append('actual responsibilities VERIFY')
        if not isinstance(out['requirements'], list) or not out['requirements'] or out['jd_ref'] == 'UNKNOWN':
            errors.append('JD requirements/snapshot VERIFY')
        for field, allowed in (('ai_involvement', AI_INVOLVEMENT),
                               ('technical_depth_requirement', TECHNICAL_DEPTH),
                               ('candidate_zone', CANDIDATE_ZONE)):
            if out[field] != 'UNKNOWN' and out[field] not in allowed:
                errors.append('invalid ' + field)
        state = 'DISCOVERED'
        if fresh and not errors:
            state = 'AUTHORITY_VERIFIED'
            if qstatus == 'VERIFY':
                state = 'QUALIFICATION_VERIFY'
            elif screen_ok:
                state = 'SCREEN_READY'
        if fresh and status['status'] == 'CLOSED':
            state = 'CLOSED'
        out.update(candidate_id=cid, role_key=key, identity=deepcopy(selected.get('identity', {})), source_status=status, intake_state=state,
                   qualification_status=qstatus, work_right=wr, sponsorship=wr['resolution_state'],
                   work_right_risks=deepcopy(wr.get('risk_flags', [])),
                   work_territory_risks=deepcopy(wr.get('territory_risks', [])),
                   work_territory_readiness=wr.get('territory_readiness', 'NOT_ASSESSED'),
                   last_verified=as_of if fresh else 'UNKNOWN', opening_status=status['status'],
                   source_capture_date=selected.get('source_capture_date', 'UNKNOWN'),
                   discovery_source=[v.get('discovery_source', 'UNKNOWN') for v in variants],
                   discovery_source_tier=[v.get('discovery_source_tier', 'UNKNOWN') for v in variants],
                   authority_source=status['refs'], official_url=selected.get('identity', {}).get('official_url', 'UNKNOWN'),
                   screen=deepcopy(screen) if screen_ok else {}, intake_issues=sorted(set(errors)),
                   unresolved_eligibility_items=[] if qstatus != 'VERIFY' else ['qualification/work-right VERIFY'],
                   raw_variants=variants, merged_from=[v.get('candidate_id', 'UNKNOWN') for v in variants],
                   provenance=[{'discovery': v.get('discovery_source'), 'observations': v.get('observations', [])} for v in variants],
                   application_status='NOT_SET_BY_INTAKE')
        candidates.append(out)
    # Any unresolved cross-group exact-key collision stays separate and cannot become active.
    for i, a in enumerate(candidates):
        for b in candidates[i+1:]:
            if any(set(identity_keys(x)) & set(identity_keys(y)) for x in a['raw_variants'] for y in b['raw_variants']):
                for c in (a,b):
                    c['intake_issues'].append('IDENTITY_VERIFY: conflicting exact-key bindings')
                    c['intake_state'] = 'DISCOVERED'
    # Conflicting IDs may hash alike; keep distinct deterministic review record identifiers.
    seen = set()
    for c in candidates:
        if c['candidate_id'] in seen:
            c['candidate_id'] += '-conflict-' + str(len(seen))
        seen.add(c['candidate_id'])
    audit = coverage_audit(candidates, batch.get('coverage_targets'), batch.get('coverage_reviewed') is True)
    return {'batch_id': batch.get('batch_id', 'UNKNOWN'), 'as_of': as_of, 'verification_mode': mode,
            'raw_count': len(raw_candidates), 'candidate_count': len(candidates), 'candidates': candidates,
            'candidate_context': deepcopy(batch.get('candidate_context')),
            'coverage_audit': audit}


def route_pool(intake, pool=None, targeted_limit=4):
    """Review proposal only. Existing pool is neither mutated nor persisted."""
    if type(targeted_limit) is not int or targeted_limit < 1:
        raise ValueError('Human-adjustable positive Targeted WIP limit required')
    pool = pool or {}
    existing = pool.get('entries', [])
    context_state, context = candidate_context_state(intake)
    active = sum(e.get('lane') == 'TARGETED' and e.get('queue_state') == 'ACTIVE' for e in existing)
    output = []
    for c in intake['candidates']:
        r = {'candidate_id': c['candidate_id'], 'company': c['company'], 'role_title': c['role_title'],
             'route': 'WATCH_VERIFY', 'lane': 'NONE', 'queue_state': 'WATCH', 'next_human_action': 'REVIEW_ROLE',
             'priority_rationale': [], 'external_action': False, 'application_status': 'NOT_SET_BY_ROUTING',
             'dimensions': deepcopy(c['screen'].get('dimensions', {})), 'job_quality': {},
             'work_right_friction': c['sponsorship'], 'pool_coverage': 'SUPPLIED' if pool else 'UNKNOWN',
             'work_right_risks': deepcopy(c.get('work_right_risks', [])),
             'work_territory_risks': deepcopy(c.get('work_territory_risks', [])),
             'work_territory_readiness': c.get('work_territory_readiness', 'NOT_ASSESSED'),
             'work_right_readiness': c.get('work_right', {}).get('routing_readiness', 'STANDARD_REVIEW'),
             'readiness_state': c.get('work_right', {}).get('routing_readiness', 'STANDARD_REVIEW'),
             'ai_involvement': c.get('ai_involvement', 'UNKNOWN'),
             'technical_depth_requirement': c.get('technical_depth_requirement', 'UNKNOWN'),
             'candidate_zone': c.get('candidate_zone', 'UNKNOWN')}
        def decide(route, action, reason, lane='NONE', queue='WATCH'):
            r.update(route=route, next_human_action=action, lane=lane, queue_state=queue, priority_rationale=[reason])
        duplicates = [e for e in existing if any(same_identity(e, v) for v in c['raw_variants'])]
        if duplicates:
            r['existing_pool_refs'] = [e.get('pool_id', 'UNKNOWN') for e in duplicates]
            decide('WATCH_VERIFY', 'HOLD', 'Exact existing pool identity; retain Applied/Closed/active status, no new work', queue='EXISTING_POOL')
        elif c['intake_state'] == 'CLOSED':
            decide('SKIP', 'SKIP', 'Inspected current official posting CLOSED; discovery mirror cannot reopen it', queue='CLOSED')
        elif context_state != 'GROUNDED':
            decide('WATCH_VERIFY', 'READ_CANDIDATE_CONTEXT',
                   'Candidate evidence/experience/eligibility context is not grounded for formal routing',
                   queue='PRELIMINARY_CONTEXT_REQUIRED')
        elif c['intake_issues']:
            decide('WATCH_VERIFY', 'REVIEW_ROLE', '; '.join(c['intake_issues']))
        elif c['qualification_status'] == 'NOT ELIGIBLE':
            if c.get('work_right', {}).get('territory_readiness') == 'NOT_VIABLE_CURRENTLY':
                decide('SKIP', 'SKIP', 'Required work territory/residence is not viable with the supplied candidate constraints; family remains open', queue='EXCLUDED')
                r['readiness_state'] = 'NOT_VIABLE_CURRENTLY'
            else:
                decide('SKIP', 'SKIP', 'Verified job-specific hard qualification/work-right failure; family remains open', queue='EXCLUDED')
        elif c['qualification_status'] != 'ELIGIBLE':
            action = ('VERIFY_CURRENT_WORK_RIGHT' if c.get('work_right', {}).get('current_work_right') == 'UNKNOWN' else
                      'VERIFY_RELOCATION_OR_START_LOCATION' if c.get('work_right', {}).get('territory_readiness') == 'RELOCATION_OR_START_LOCATION_VERIFY' else
                      'VERIFY_WORK_TERRITORY' if c.get('work_right', {}).get('territory_readiness') == 'WORK_TERRITORY_VERIFY' else
                      'VERIFY_SPONSORSHIP' if c['sponsorship'] in {'SPONSORSHIP_VERIFY','OTHER_ROUTE_VERIFY'} else
                      'VERIFY_ELIGIBILITY')
            reason = ('Work territory/residence feasibility remains open; no capability/evidence history is changed'
                      if action in {'VERIFY_RELOCATION_OR_START_LOCATION', 'VERIFY_WORK_TERRITORY'}
                      else 'Work-right/qualification remains open; no geography penalty')
            decide('WATCH_VERIFY', action, reason)
            if action == 'VERIFY_CURRENT_WORK_RIGHT':
                r['readiness_state'] = 'WATCH_VERIFY_CURRENT_WORK_RIGHT'
            elif action in {'VERIFY_RELOCATION_OR_START_LOCATION', 'VERIFY_WORK_TERRITORY'}:
                r['readiness_state'] = c.get('work_right', {}).get('territory_readiness', 'WORK_TERRITORY_VERIFY')
            elif c.get('work_right_risks'):
                r['readiness_state'] = 'LONG_TERM_ELIGIBILITY_RISK'
        else:
            s = c['screen']
            dimensions = s.get('dimensions', {})
            if not isinstance(dimensions, dict):
                dimensions = {}
            valid_dimensions = all(isinstance(dimensions.get(d), dict) and dimensions[d].get('rationale')
                                   and dimensions[d].get('refs') for d in DIMENSIONS)
            if not valid_dimensions or not s.get('evidence_refs') or not s.get('responsibility_match'):
                decide('WATCH_VERIFY', 'REVIEW_ROLE', 'Grounded light screen/evidence match missing')
            else:
                observations = [o for o in s.get('quality_observations', []) if isinstance(o, dict) and o.get('basis') == 'ROLE_EVIDENCE']
                quality = quality_review({'capability_fit': s.get('responsibility_match'),
                                          'base_recommendation': 'Apply', 'observations': observations})
                r['job_quality'] = quality
                r['calibration_context'] = deepcopy(s.get('calibration_context', 'UNKNOWN'))
                if quality['concerns']:
                    decide('WATCH_VERIFY', 'VERIFY_JOB_QUALITY', 'Material Job Quality downgrade; benefit/salary positives cannot cancel known risks')
                elif s.get('severe_mismatch') in {'CAPABILITY', 'WORK_STYLE', 'JOB_QUALITY', 'VALUE_COST'} and s.get('mismatch_refs') and s.get('mismatch_reason'):
                    decide('SKIP', 'SKIP', s['mismatch_reason'], queue='EXCLUDED')
                elif s.get('critical_unknowns'):
                    decide('WATCH_VERIFY', 'REVIEW_ROLE', 'Decision-changing unknowns: ' + '; '.join(s['critical_unknowns']))
                elif s.get('company_constraint') != 'CLEAR':
                    decide('WATCH_VERIFY', 'HOLD', 'Company application constraint/slot unresolved')
                elif pool.get('company_constraints', {}).get(c['company']) in {'FULL','VERIFY'}:
                    decide('WATCH_VERIFY', 'HOLD', 'Existing pool company constraint prevents another active role')
                elif s.get('responsibility_match') in {'STRONG','DEFENSIBLE_STRETCH'} and s.get('career_value') == 'HIGH':
                    queued = active >= targeted_limit
                    decide('TARGETED_PREPARE', 'HOLD' if queued else 'RUN_ANALYSE_JOB',
                           'High Career Value and grounded responsibility match; ' + ('Targeted WIP full' if queued else 'deeper evidence routing justified'),
                           'TARGETED', 'QUEUED' if queued else 'ACTIVE')
                    r['targeted_state'] = 'TARGETED_CANDIDATE / QUEUED' if queued else 'ACTIVE'
                    if not queued:
                        active += 1
                elif s.get('responsibility_match') in {'STRONG','REASONABLE','DEFENSIBLE_STRETCH'} and s.get('application_cost') == 'LOW':
                    decide('FAST_APPLY', 'FAST_APPLICATION_REVIEW', 'Viable honest evidence match, reasonable value and low application cost', 'FAST', 'REVIEW')
                    r['readiness_state'] = 'FAST_READY'
                else:
                    decide('WATCH_VERIFY', 'REVIEW_ROLE', 'Value/effort trade-off needs Human review')
        output.append(r)
    continuity = []
    for entry in existing:
        if any(any(same_identity(entry, variant) for variant in candidate['raw_variants'])
               for candidate in intake['candidates']):
            continue
        pool_ref = entry.get('pool_id', 'UNKNOWN')
        closed = entry.get('application_status') == 'CLOSED' or entry.get('queue_state') == 'CLOSED'
        continuity.append({'pool_id': pool_ref, 'candidate_id': entry.get('candidate_id', 'UNKNOWN'),
                           'company': entry.get('company', 'UNKNOWN'), 'role_title': entry.get('role_title', 'UNKNOWN'),
                           'continuity_state': 'CLOSED' if closed else 'NEEDS_REVALIDATION',
                           'previous_lane': entry.get('lane', 'UNKNOWN'),
                           'reason': ('Previously closed record retained for history' if closed else
                                      'Existing pool candidate absent from latest batch; restore to comparison after current revalidation')})
    targeted = [r for r in output if r['route'] == 'TARGETED_PREPARE']
    fast = [r for r in output if r['route'] == 'FAST_APPLY']
    return {'candidate_status': 'HUMAN_REVIEW_REQUIRED', 'routing_state': context_state,
            'candidate_context': context, 'targeted_limit': targeted_limit,
            'targeted_wip_applies_to': 'DEEP_ANALYSIS_AND_MATERIAL_PREPARATION_ONLY',
            'opportunity_pool_count': len(output) + len(continuity),
            'targeted_candidate_count': len(targeted),
            'targeted_active_count': sum(r.get('queue_state') == 'ACTIVE' for r in targeted),
            'fast_lane_count': len(fast), 'existing_pool_continuity': continuity,
            'allocation_order': 'supplied batch order; Human may reorder by explained dimensions, no total score',
            'ai_neutral_by_default': True, 'routes': output, 'external_action': False}
