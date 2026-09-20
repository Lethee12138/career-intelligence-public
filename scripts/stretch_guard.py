"""Checks manually grounded claim/use boundaries, not prose truth or entailment.

Callers must review atom extraction, source attribution, and L1-L3 substance.
No source I/O, scoring, permissions grant, new matching engine or live gate.
"""
from guard import match_errors

USES = {'positioning', 'role_hypothesis', 'fit_discussion', 'resume_framing',
        'interview_bridge', 'project_selection', 'recruiter_concern'}
HARD = {'identity', 'metric', 'number', 'date', 'employment', 'official_title',
        'qualification', 'certification', 'production_deployment', 'commercial_impact',
        'user_adoption', 'client_adoption', 'team_size', 'participant_count',
        'technical_stack', 'formal_ownership', 'management_responsibility'}


def present(value):
    return isinstance(value, str) and bool(value.strip()) and value.strip() != 'UNKNOWN'


def stretch_errors(claim, evidence_ids):
    errors = []
    boundary = claim.get('use_boundary')
    if boundary not in {'VERIFIED_FACT', 'DEFENSIBLE_STRETCH', 'SPECULATIVE_UNSUPPORTED'}:
        errors.append('invalid use boundary')
    refs = claim.get('evidence_refs', [])
    if not refs or any(r not in evidence_ids for r in refs):
        errors.append('unresolved evidence refs')
    if boundary == 'VERIFIED_FACT':
        if claim.get('proposition_verified') is not True or not present(claim.get('verification_scope')):
            errors.append('bounded proposition not verified')
    if boundary == 'DEFENSIBLE_STRETCH':
        for k in ('bridge_reasoning', 'unproven_scope', 'prohibited_overclaim', 'ownership_boundary', 'context_rationale'):
            if not present(claim.get(k)):
                errors.append('missing ' + k)
        if not claim.get('source_capability_refs'):
            errors.append('missing source capability')
        for k in ('adjacency_reviewed', 'ownership_reviewed', 'followup_reviewed'):
            if claim.get(k) is not True:
                errors.append(k + ' required')
        if claim.get('direct_counterevidence') is not False:
            errors.append('counterevidence unresolved or contradicts stretch')
        if claim.get('invents_credential') is not False:
            errors.append('credential boundary unresolved or violated')
        uses = claim.get('allowed_use', [])
        if not uses or not set(uses) <= USES:
            errors.append('invalid allowed use')
        if set(uses) & {'resume_framing', 'interview_bridge'}:
            d = claim.get('defensibility', {})
            for level in ('L1', 'L2', 'L3'):
                if not present(d.get(level)):
                    errors.append('missing defensibility ' + level)
            if d.get('reviewed') is not True:
                errors.append('defensibility requires substantive review')
    if boundary == 'SPECULATIVE_UNSUPPORTED' and claim.get('allowed_use'):
        errors.append('unsupported claim cannot enter affirmative packaging')
    return errors


def fact_atom_errors(atoms, source_atoms):
    """Atoms are reviewed (type, source_id, value, scope), never inferred from text.

    Equality preserves both value and scope. A source atom is not necessarily a
    candidate verified fact: report-attributed premises must stay attributed.
    """
    errors = []
    for atom in atoms:
        key = atom.get('source_id')
        source = source_atoms.get(key)
        if atom.get('type') not in HARD or not source:
            errors.append('unknown hard fact or source')
        elif any(atom.get(k) != source.get(k) for k in ('type', 'value', 'scope')):
            errors.append('hard fact expansion: ' + str(key))
    return errors


def stretch_match_errors(row, claim, evidence):
    errors = match_errors(row, evidence, completed_only=True)
    errors += stretch_errors(claim, set(evidence))
    if claim.get('use_boundary') == 'DEFENSIBLE_STRETCH' and row.get('match_level') != 'PARTIAL':
        errors.append('stretch match must remain PARTIAL')
    if claim.get('use_boundary') == 'SPECULATIVE_UNSUPPORTED' and row.get('match_level') not in {'UNSUPPORTED', 'UNKNOWN'}:
        errors.append('unsupported bridge cannot support positive match')
    if not set(claim.get('evidence_refs', [])) <= set(row.get('evidence_refs', [])):
        errors.append('match lost bridge evidence refs')
    return errors


def trace_errors(nodes, chain):
    """Check explicit stage lineage; source IDs cannot be replaced by similar names."""
    stages = ['preparation', 'analysis', 'discovery', 'position', 'evidence']
    errors = []
    if len(chain) != len(stages):
        return ['five-stage reverse trace required']
    for i, (key, stage) in enumerate(zip(chain, stages)):
        node = nodes.get(key, {})
        if node.get('stage') != stage:
            errors.append('missing/wrong stage: ' + key)
        if i < len(chain)-1 and chain[i+1] not in node.get('input_refs', []):
            errors.append('broken edge: ' + key)
    p, a = (nodes.get(chain[i], {}) for i in (0, 1))
    if not present(p.get('role_key')) or p.get('role_key') != a.get('role_key'):
        errors.append('preparation/analysis job identity mismatch')
    return errors
