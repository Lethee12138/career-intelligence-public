# Market Discovery Profile

The profile is caller-scoped configuration, not candidate evidence or a universal Career policy. The public runtime loads `references/market-discovery-profile.default.json`; callers may overlay private values through `careerContext.market_discovery_profile` without committing them to this repository.

Supported fields:

- `profile_id`, `profile_version`, `profile_kind`
- `company_priority`: company-size, big-tech, familiar-brand and adapter policies
- `company_coverage_buckets[]`
- `decision_priority[]`
- `work_style_negative_signals[]`
- `market_location_preferences`
- `location_ordering[]`
- `market_specific_exceptions[]`
- `coverage_safeguard`: minimum known candidates, head buckets, share threshold, supplement buckets, evidence-ref requirement, UNKNOWN handling and maximum supplement passes

The neutral public default contains no personal role, city, work-style, application, CV or evidence values. The example profile is synthetic. Private hosts should keep real preferences outside the repository.
