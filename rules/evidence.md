# Evidence contract

The existing Master Evidence/project fact card is the fact owner. Keep a task-local index of references, not a maintained second bank. A test fixture is a redacted historical excerpt, never a production evidence input. Resolve exact project/evidence IDs plus location and revision; semantic similarity is insufficient.

For each used item support: source, source location, ownership scope, context, action/decision, method/tool, result/output, limitation/boundary, metric scope, confidence/uncertainty, public-use boundary, resume-use boundary, last verified where known. Any absent field is `UNKNOWN`; analysis can proceed with partial metadata. Preserve source author (`DIRECT_USER`, `ACCEPTED_RECORD`, `ASSISTANT_REPORT`, `EXTERNAL_REPORT`, `UNKNOWN`) separately from confidence.

Never infer commercial outcomes, ownership, user counts, efficiency gain, deployment, quantitative improvement or technical expertise from resume wording. A fact card may support a prototype; that does not support production deployment or employment as a software engineer. A repository proves only what was inspected, not personal authorship or client adoption.

Every SUPPORTED or PARTIAL requirement match must cite a real inspected evidence location and state exactly what it supports and excludes. UNSUPPORTED means a bounded search found no support in the reviewed evidence; it does not establish that the candidate can never do it. UNKNOWN means coverage/access/context is inadequate. Distinguish a Capability gap from an Evidence gap.

Respect task/batch-specific eligibility of evidence. Freeze the evidence cutoff and exclusions in the analysis. A task or batch may exclude active private project development while allowing a specifically reviewed completed artifact. Later work does not retroactively change an earlier evidence cutoff. Keep source scope and read-only boundaries explicit.

Metrics retain numerator/denominator where relevant, unit, population, period, method and scope. Rounds ≠ participants; exploratory responses ≠ representative market research. Classify new metric information as CORRECTION, NEW_SNAPSHOT, SCOPE_CLARIFICATION or LATER_DEVELOPMENT. Preserve old snapshots; propose reconciliation for Human Review without writeback. Aggregate “9+ documented changes” does not justify inventing nine individual change events.
