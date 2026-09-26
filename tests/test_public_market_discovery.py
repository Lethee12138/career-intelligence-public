import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import career_scan


ROOT = Path(__file__).resolve().parents[1]


def candidate(company, role, bucket):
    return {
        "company": company,
        "exact_role": role,
        "company_coverage_bucket": bucket,
        "official_source": {
            "url": f"https://example.invalid/jobs/{company.lower().replace(' ', '-')}",
            "exact_role_verified": False,
            "inspected_original": False,
        },
        "live_status": "VERIFY",
    }


def market_run(candidates=None, **extra):
    discovery = {
        "provider": "EXTERNAL_WEB_DISCOVERY_HANDOFF",
        "candidates": candidates or [],
        **extra,
    }
    return career_scan.run_scan_review(
        None,
        {},
        use_current_career_context=False,
        mode="market_discovery",
        discovery=discovery,
    )


class PublicMarketDiscoveryTests(unittest.TestCase):
    def test_no_company_request_returns_neutral_handoff(self):
        result = career_scan.run_scan_review(
            None,
            {},
            use_current_career_context=False,
            mode="market_discovery",
            discovery={"roleHypotheses": [{"id": "SYN-H1", "role_or_family": "Product"}]},
        )
        self.assertEqual(result["discovery"]["state"], "HANDOFF_REQUIRED")
        plan = result["discovery"]["handoff"]["coverage_plan"]
        self.assertEqual(plan["default_profile_id"], "PUBLIC_NEUTRAL_MARKET_DISCOVERY_PROFILE")
        self.assertIn("MID_LARGE_TECH", plan["company_coverage_buckets"])
        self.assertFalse(plan["generic_discovery"]["dedicated_adapters_are_market_boundary"])

    def test_unconfigured_generic_candidates_are_accepted(self):
        result = market_run([
            candidate("Example MidTech", "Product Associate", "MID_LARGE_TECH"),
            candidate("Example SaaS", "Product Researcher", "SAAS_ENTERPRISE_SOFTWARE"),
        ])
        self.assertEqual(result["discovery"]["state"], "RESULTS_INGESTED")
        self.assertEqual(result["summary"]["discovery_candidate_count"], 2)
        self.assertTrue(all(row["next_action"] == "VERIFY_OFFICIAL_SOURCE" for row in result["pool_view"]["candidates"]))

    def test_candidate_only_ingest_does_not_require_role_hypotheses(self):
        result = market_run([candidate("Example AI App", "AI Product Associate", "AI_NATIVE_APPLICATION")])
        self.assertEqual(result["discovery"]["role_hypothesis_count"], 0)
        self.assertEqual(result["discovery"]["candidate_count"], 1)

    def test_balanced_non_head_set_does_not_trigger_imbalance(self):
        result = market_run([
            candidate("Example MidTech", "Product Associate", "MID_LARGE_TECH"),
            candidate("Example SaaS", "Digital Product Associate", "SAAS_ENTERPRISE_SOFTWARE"),
            candidate("Example AI App", "AI Product Associate", "AI_NATIVE_APPLICATION"),
            candidate("Example Global Team", "Research Associate", "FOREIGN_INTERNATIONAL_TEAM"),
        ])
        self.assertEqual(result["discovery"]["coverage_state"], "COVERAGE_REVIEWED")
        self.assertEqual(result["discovery"]["continuation_state"], "COMPLETE_FOR_CURRENT_SCOPE")

    def test_head_concentration_triggers_one_supplement(self):
        rows = [candidate(f"Example Head Tech {n}", f"Product Role {n}", "LARGE_INTERNET_TECH") for n in range(4)]
        result = market_run(rows)
        self.assertEqual(result["discovery"]["coverage_state"], "DISCOVERY_COVERAGE_IMBALANCE")
        self.assertEqual(result["discovery"]["continuation_state"], "SUPPLEMENT_REQUIRED")
        self.assertIn("SAAS_ENTERPRISE_SOFTWARE", result["discovery"]["supplemental_handoff"]["company_coverage_buckets"])

    def test_market_evidence_override_requires_refs(self):
        rows = [candidate(f"Example Head Tech {n}", f"Product Role {n}", "LARGE_INTERNET_TECH") for n in range(4)]
        bare = market_run(rows, providerRun={"coverage_evidence": {"head_concentration_supported": True}})
        grounded = market_run(rows, providerRun={"coverage_evidence": {"head_concentration_supported": True, "refs": ["SYN-MARKET-REF"]}})
        self.assertEqual(bare["discovery"]["coverage_state"], "DISCOVERY_COVERAGE_IMBALANCE")
        self.assertEqual(grounded["discovery"]["coverage_state"], "COVERAGE_REVIEWED")

    def test_completed_supplement_prevents_infinite_loop(self):
        rows = [candidate(f"Example Head Tech {n}", f"Product Role {n}", "LARGE_INTERNET_TECH") for n in range(4)]
        result = market_run(rows, providerRun={"coverage_supplement_pass": True})
        self.assertFalse(result["discovery"]["coverage"]["supplement_required"])
        self.assertTrue(result["discovery"]["coverage"]["supplement_pass_already_completed"])
        self.assertNotIn("supplemental_handoff", result["discovery"])

    def test_hybrid_merges_and_dedupes(self):
        configured = career_scan._empty_scan("SYN-SCAN", "2026-09-26T00:00:00+00:00")
        existing = career_scan._normalize_discovery_candidate(
            candidate("Example MidTech", "Product Associate", "MID_LARGE_TECH"),
            {"schema_version": "0.2.4"},
        )
        configured["candidate_pool"] = [existing]
        configured["raw_record_count"] = 1
        configured["deduped_count"] = 1
        with patch.object(career_scan, "resolve_scan_config", return_value={"sources": [{"adapter": "example"}]}), patch.object(career_scan, "run_batch", return_value=configured):
            result = career_scan.run_scan_review(
                None, {}, use_current_career_context=False, mode="hybrid_discovery",
                discovery={"candidates": [candidate("Example MidTech", "Product Associate", "MID_LARGE_TECH"), candidate("Example SaaS", "Research Associate", "SAAS_ENTERPRISE_SOFTWARE")]},
            )
        self.assertEqual(result["scan"]["deduped_count"], 2)

    def test_configured_review_keeps_configured_source_scope(self):
        configured = career_scan._empty_scan("SYN-SCAN", "2026-09-26T00:00:00+00:00")
        with patch.object(career_scan, "resolve_scan_config", return_value={"sources": [{"adapter": "example", "mode": "discover"}]}), patch.object(career_scan, "run_batch", return_value=configured):
            result = career_scan.run_scan_review(None, {}, use_current_career_context=False, mode="configured_review")
        self.assertEqual(result["mode"], "configured_review")
        self.assertEqual(result["discovery"]["state"], "NOT_REQUESTED")
        self.assertEqual(result["source_scope"]["sources"][0]["adapter"], "example")

    def test_public_profiles_are_neutral_and_synthetic(self):
        default = json.loads((ROOT / "references/market-discovery-profile.default.json").read_text())
        example = json.loads((ROOT / "references/market-discovery-profile.example.json").read_text())
        self.assertEqual(default["decision_priority"], [])
        self.assertEqual(default["location_ordering"], [])
        self.assertEqual(default["work_style_negative_signals"], [])
        self.assertIn("SYNTHETIC / EXAMPLE ONLY", example["notice"])

    def test_public_tree_contains_no_private_runtime_or_secret_markers(self):
        text = "\n".join(
            path.read_text(errors="ignore")
            for path in ROOT.rglob("*")
            if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts
        )
        forbidden = [
            chr(47) + "Users" + chr(47) + "luna" + chr(47),
            ".codex" + chr(47) + "attachments" + chr(47),
            "PRIVATE_RUNTIME_" + "REFERENCE",
            "DEPRIORITIZED_UNLESS_" + "HIGH_CAREER_VALUE",
            "CAREER_MARKET_DISCOVERY_" + "DEFAULT_PROFILE",
        ]
        self.assertEqual([value for value in forbidden if value in text], [])
        self.assertIsNone(re.search(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}", text))


if __name__ == "__main__":
    unittest.main()
