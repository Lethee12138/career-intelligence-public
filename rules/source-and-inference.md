# Sources, identity and uncertainty

Represent each claim using two independent labels:

- Epistemic kind: `FACT`, `EXTERNAL_REPORT`, `INFERENCE`, `UNKNOWN`.
- Source level: `CONFIRMED / AUTHORITY SOURCE`, `RELIABLE EXTERNAL`, `COMMUNITY / ANECDOTAL`, `REASONABLE INFERENCE`, `UNKNOWN`.

A candidate fact from an accepted fact card can be FACT; a historical analyst summary of an official webpage is still an EXTERNAL_REPORT in this run unless the official snapshot is inspected. A plausible product scenario is INFERENCE even if the product itself exists. Company/BG/product existence never establishes a vacancy or actual HC.

China tiers:

| Tier | Discovery/source type |
|---|---|
| 1 | Company official careers, official ATS, official recruitment notice |
| 2 | Official/public employment and state-owned recruitment services |
| 3 | BOSS, Liepin, Zhaopin, 51job, LinkedIn, Indeed, Nowcoder calendar, university careers |
| 4 | Maimai, referral groups, social posts, comments, DMs |

Tier is not proof of authority for every claim. A Tier 2 general notice may not verify a specific role. Preserve discovery source and authority source separately. Qualification, deadline, assessments and application status require role/programme-specific authority or a formally verifiable channel before submission (submission itself is outside this skill). “免笔试”, “急招”, “AI 推荐” do not relax verification.

Bind sources to employer, requisition ID or exact official URL, recruitment batch, location and revision. Title-only similarity cannot merge jobs. A missing ID may use an exact URL; if neither is available, mark identity VERIFY and block preparation. Preserve existing Job Record identity and source history; a changed JD needs new analysis, not silent reuse.

Compare claim-specific authority, scope and observation dates. Exact matching authority CLOSED/FILLED overrides an apparently open discovery mirror. Confirmed explicit closure yields CLOSED at that snapshot; inaccessible/removed/404 alone or conflicting authority snapshots with ambiguous ordering yields VERIFY. A later discovery OPEN cannot reopen a closed authority record. An explicit newer authority OPEN can reopen only the same verified identity. An old snapshot is not a current verification, and `analysis_date` is not `last_verified_at`.

Offline mode: record `as_of`, `last_verified_at`, `verification_mode=HISTORICAL_SNAPSHOT`; status is historical and not usable for live preparation without revalidation. Never silently stamp today's date onto old official-source claims.
