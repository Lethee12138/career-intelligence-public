# Capability Profile

Use the existing [claim and evidence contract](contracts.md) for each substantive statement and every reference. Do not create a second evidence owner. Apply [discovery rules](../rules/discovery.md).

Report envelope: schema_version, HUMAN_REVIEW_REQUIRED, as_of, evidence_cutoff, source_coverage, excluded_evidence, existing_profile_ref, industry_scope=OPEN (or sourced exclusions), preference_refs, education_context, questioning_stop_reason.

Each capability: id; capability_name; epistemic_status (SELF_IDENTIFIED / DEMONSTRATED / INFERRED / POTENTIAL); evidenceRefs; contexts; repetition_signal (specific shared behavior and distinct contexts, or strong-single justification); ownership_strength (CLEAR / PARTIAL / UNKNOWN) and ownership_boundary; limitations; counterevidence_or_missing_evidence; transferability_hypothesis; market_language_variants; confidence (STRONG / MODERATE / TENTATIVE); deduplication_disposition with existing exact reference or reason new.

Output inventory: project/evidence reference, completion_at_cutoff, working/interactive/playable status, phase-specific contributions (research, framing, workflow/system, product decisions, prototyping, AI implementation, tests, iteration), Human/AI/team boundary and unknowns. Reuse evidence items by reference rather than copying full source documents.

Seed review: seed role; why candidate considers it (UNKNOWN if no explicit reason); supports; counters; gaps; possible misconception labelled inference; adjacent alternatives; market observations needed to confirm/weaken. Role pool uses the [role hypothesis contract](role-hypothesis.md).

Readable order: bounded conclusion → output inventory → capabilities with limitations → seed counter-check → role pool → only decision-changing unknowns and next validation. Group common source limits once, keeping affected claims traceable. No speculative CV claims or automatic adoption.
