"""Reproduce the explicit synthetic E2E fixture, never perform search or submission."""
import json
from pathlib import Path
from search_execution import make_handoff, intake_batch, route_pool
from guard import match_errors, assessment_errors, preparation_gate, claim_errors
from discovery_guard import capability_errors, route_errors, market_update
from stretch_guard import stretch_match_errors

ROOT = Path(__file__).resolve().parents[1]


def run_fixture():
    f = json.loads((ROOT / 'tests/fixtures/search-execution.json').read_text())
    assert f['test_only'] is True and f['verification_mode'] == 'SYNTHETIC_LIVE_CONTROL'
    day = f['as_of']
    records = {'SYN-E1': {'source_ref': 'search-execution.json#evidence/SYN-E1', 'locator': 'SYN-E1',
                          'direct_verified': True, 'supports_bounded_capability': True}}
    cap = {'id': 'C1', 'epistemic_status': 'DEMONSTRATED', 'confidence': 'MODERATE', 'evidenceRefs': ['SYN-E1']}
    bridge = {'capability_id': 'C1', 'problem': 'Human decisions lost in workflow handoffs',
              'team': 'Internal product/workflow team', 'role': 'Reviewable workflow design'}
    assert not capability_errors(cap, records)
    assert not route_errors('B', bridge, {'C1': cap}, records)
    discovery = f['discovery']
    discovery_result = {'id':'SYN-DISCOVERY', 'mode':'ANALYSIS_ONLY', 'capability_profile': cap,
                        'route_B_bridge': bridge, 'role_hypotheses':discovery['role_hypotheses'],
                        'route_coverage': {'A':'No seed role supplied; title counter-check in hypotheses',
                            'B':'Synthetic demonstrated prototype evidence', 'C':'No repeated inferred behavior supplied',
                            'D':'One problem context only; no fabricated repeated pattern'},
                        'input_refs':['SYN-POSITION','SYN-E1'], 'evidence_boundary':f['boundary']}
    handoff = make_handoff(discovery, 'SYN-SEARCH-01', day, f['pool'])
    intake = intake_batch(f['batch'], day, 'LIVE')  # simulated same-day original assertions only
    routed = route_pool(intake, f['pool'], f['targeted_limit'])
    chains = []
    for company, lane in [('Synthetic sz','TARGETED'), ('Synthetic hz','FAST')]:
        c = next(c for c in intake['candidates'] if c['company'] == company)
        route = next(r for r in routed['routes'] if r['candidate_id'] == c['candidate_id'])
        assert route['lane'] == lane
        requirement_matches = [
            {'requirement_id':'R1','requirement_text':c['requirements'][0]['text'],
             'requirement_source_location':c['jd_ref'], 'hierarchy':'MUST','match_level':'SUPPORTED',
             'evidence_refs':['SYN-E1'],'supported_scope':'Synthetic prototype of human review checkpoints',
             'unsupported_scope':'No commercial adoption or production model expertise','gap_types':[],'uncertainty':'Synthetic evidence only'},
            {'requirement_id':'R2','requirement_text':c['requirements'][1]['text'],
             'requirement_source_location':c['jd_ref'], 'hierarchy':'STRONG PREFERENCE','match_level':'PARTIAL',
             'evidence_refs':['SYN-E1'],'supported_scope':'Transferable evaluation framing from a review prototype',
             'unsupported_scope':'No production model evaluation, Agent/RAG deployment or commercial metrics',
             'gap_types':['EXPERIENCE','EVIDENCE'],'uncertainty':'Defensible stretch, not direct expertise'}]
        stretch = {'use_boundary':'DEFENSIBLE_STRETCH','evidence_refs':['SYN-E1'],'source_capability_refs':['C1'],
                   'bridge_reasoning':'Designing a review checkpoint transfers to framing human evaluation steps',
                   'unproven_scope':'Production model evaluation','prohibited_overclaim':'No Agent/RAG or commercial outcome claims',
                   'ownership_boundary':'Synthetic prototype only','context_rationale':'Adjacent review responsibilities',
                   'adjacency_reviewed':True,'ownership_reviewed':True,'followup_reviewed':True,
                   'direct_counterevidence':False,'invents_credential':False,'allowed_use':['fit_discussion','project_selection']}
        checks = [match_errors(r, f['evidence']) for r in requirement_matches]
        stretch_checks = stretch_match_errors(requirement_matches[1], stretch, f['evidence'])
        assert not any(checks) and not stretch_checks
        analysis = {'id':c['candidate_id']+'-ANALYSIS-v1','schema_version':'0.2',
                    'candidate_status':'HUMAN_REVIEW_REQUIRED','role_key':c['role_key'],
                    'job_identity':{k:c[k] for k in ('company','role_title','employment_market','country','city','company_type','official_url')},
                    'existing_job_record_ref':'NOT_APPLICABLE: synthetic new candidate', 'analysis_date':day,'as_of':day,
                    'verification_mode':'SYNTHETIC_LIVE_CONTROL','evidence_cutoff':day,
                    'source_coverage':['Synthetic exact authority snapshot','SYN-E1'], 'excluded_evidence':['all real candidate records'],
                    'source_status':c['source_status'],'qualification':c['qualification_status'],
                    'qualification_checks':c['raw_variants'][0]['qualification_review']['checks'],
                    'job_facts':{k:c[k] for k in ('deadline','official_published_date','responsibilities','requirements','opening_status','last_verified')},
                    'work_right':c['work_right'],'matches':requirement_matches,'stretch':stretch,
                    'actual_role_interpretation':{'kind':'INFERENCE','refs':[c['jd_ref']],
                        'value':'Make human-review workflow usable and testable; title is secondary'},
                    'dimensions':c['screen']['dimensions'],'job_quality':route['job_quality'],
                    'gaps':[{'type':'EXPERIENCE','scope':requirement_matches[1]['unsupported_scope'],'impact':'Preferred gap stays visible'}],
                    'risks':['Production evaluation experience gap','Real CV Base/version and source permissions not part of synthetic input'],
                    'recommendation':'High Priority Apply' if lane=='TARGETED' else 'Apply',
                    'rationale':route['priority_rationale'],
                    'decisive_positives':['Bounded prototype evidence fits actual duties'],
                    'decisive_negatives':['No direct production model experience'],
                    'what_would_change_it':['Real authority/eligibility changes','Severe team quality signal'],
                    'alternatives':['Retain responsibility hypothesis if this job closes'],
                    'evidence_justifies_preparation':True,'critical_unknowns':[],'one_active_application':False,
                    'input_refs':[c['candidate_id'],'SYN-DISCOVERY','SYN-E1']}
        assert not assessment_errors(analysis)
        gate = preparation_gate(analysis)
        fact = {'F1':{'evidence_id':'SYN-E1','verified':True,'source_location':'fixture SYN-E1',
                      'supported_capabilities':['review checkpoint prototype']}}
        claim = {'requirement_id':'R1','evidence_id':'SYN-E1','fact_id':'F1',
                 'text':'Designed a review-checkpoint prototype (synthetic demonstration only).',
                 'scope_reviewed':True,'asserted_capabilities':['review checkpoint prototype']}
        claim_check = claim_errors(claim, {'R1','R2'}, f['evidence'], fact)
        assert not claim_check
        brief = {'id':c['candidate_id']+'-BRIEF-v1','role_key':c['role_key'],'analysis_ref':analysis['id'],
                 'input_refs':[analysis['id']],'candidate_status':'HUMAN_REVIEW_REQUIRED',
                 'verification_mode':'SYNTHETIC_LIVE_CONTROL','gate':gate['gate'],'gate_reasons':gate['reasons'],
                 'lane':lane,'why_role':analysis['rationale'],
                 'existing_CV_Base':{'name':'UNKNOWN','version':'UNKNOWN','action':'Locate existing authorized base for real use; no source CV created'},
                 'project_router':[{'evidence_ref':'SYN-E1','why':'Direct bounded prototype support for R1','exclude':'No commercial/deployment claims'}],
                 'portfolio':'NOT_APPLICABLE: no public-use permission in synthetic fixture',
                 'recruiter_concerns':['Can this transfer to production evaluation?'],
                 'honest_gap_response':'I can explain review-flow decisions; production AI evaluation remains unproven.',
                 'interview_story':{'context':'Human review checkpoints','decision':'Make review explicit',
                     'output':'Synthetic review prototype','followup':'Explain judgment vs implementation boundaries',
                     'answer_boundary':'No production/Agent/RAG or business metrics'},
                 'claim_candidates':[claim] if gate['gate']=='READY_FOR_REVIEW' else [],
                 'packet':None,
                 'preparation_checklist':(['Review all requirement/evidence rows','Select bounded prototype story','Resolve real CV permissions and source version']
                    if lane=='TARGETED' else ['Check qualification and two evidence rows','Use one existing-base draft after permission check']),
                 'VERIFY':['Real CV source/version and adoption permissions remain outside this synthetic demonstration',
                           'Real opening, sponsorship and law must be verified before real use'],
                 'adoption':'NOT_AUTHORIZED; synthetic evidence and job only', 'external_action':False}
        historical = dict(analysis, source_status={**analysis['source_status'], 'live_verified':False})
        assert preparation_gate(historical)['gate']=='PREPARATION_HOLD'
        chains.append({'candidate_id':c['candidate_id'],'lane':lane,'analysis':analysis,'brief':brief,
                       'checks':{'match_errors':checks,'stretch_errors':stretch_checks,'assessment_errors':[],
                                 'claim_errors':claim_check,'historical_control_gate':preparation_gate(historical)}})
    summary = [{k:v for k,v in c.items() if k not in {'raw_variants','screen'}} for c in intake['candidates']]
    return {'test_only':True,'verification_mode':'SYNTHETIC_LIVE_CONTROL','boundary':f['boundary'],
            'discovery':discovery_result,'handoff':handoff,'raw_batch_ref':'tests/fixtures/search-execution.json#batch',
            'intake':{**{k:v for k,v in intake.items() if k!='candidates'},'candidates':summary},
            'routed_pool':routed,'selected_deep_analysis_count':2,'chains':chains,
            'external_search_performed':False,'external_application_performed':False}


if __name__ == '__main__':
    result = run_fixture()
    path = ROOT / 'tests/outputs/search-execution-trace.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('SYNTHETIC E2E PASS:',result['intake']['raw_count'],'raw ->',result['intake']['candidate_count'],
          'candidates;',len(result['chains']),'selected chains; no external action')
    for r in result['routed_pool']['routes']:
        print(r['company'],r['route'],r['queue_state'],r['next_human_action'])
