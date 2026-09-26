import json
import os
import shutil
import socket
import subprocess
import time
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp/career-mcp-http-server.mjs"
REQUIRE_BASE = os.environ.get("CAREER_MCP_REQUIRE_BASE")
DEFAULT_REQUIRE_BASE = Path(REQUIRE_BASE) if REQUIRE_BASE else None


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _mcp_post(port, payload):
    request = Request(
        f"http://127.0.0.1:{port}/mcp",
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        raw = response.read().decode()
    lines = [line[6:] for line in raw.splitlines() if line.startswith("data: ")]
    return json.loads(lines[-1] if lines else raw)


@unittest.skipUnless(
    shutil.which("node") and DEFAULT_REQUIRE_BASE is not None and DEFAULT_REQUIRE_BASE.exists(),
    "requires Node and an already-installed official MCP SDK dependency base",
)
class CareerMcpHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        env = os.environ.copy()
        env["CAREER_MCP_HTTP_PORT"] = str(cls.port)
        env["CAREER_MCP_REQUIRE_BASE"] = str(DEFAULT_REQUIRE_BASE)
        cls.context_dir = tempfile.TemporaryDirectory()
        context_path = Path(cls.context_dir.name) / "synthetic-context.json"
        context_path.write_text(json.dumps({"context_version":"SYNTHETIC","as_of":"2026-09-26","existing_roles":[],"candidate_context":{},"preference_context":{}}))
        env["CAREER_CONTEXT_PATH"] = str(context_path)
        cls.process = subprocess.Popen(
            ["node", str(SERVER)],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with urlopen(
                    f"http://127.0.0.1:{cls.port}/healthz", timeout=1
                ) as response:
                    if json.loads(response.read())["ok"]:
                        return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("career MCP server did not become healthy")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()
        cls.context_dir.cleanup()

    def test_tools_list_exposes_only_bounded_read_tools(self):
        response = _mcp_post(
            self.port,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        tools = response["result"]["tools"]
        names = [tool["name"] for tool in tools]
        self.assertEqual(
            names, ["career.server_info", "career.scan_and_review"]
        )
        for tool in tools:
            self.assertTrue(tool["annotations"]["readOnlyHint"])
            self.assertFalse(tool["annotations"]["destructiveHint"])
            self.assertIn("outputSchema", tool)

        scan_tool = next(tool for tool in tools if tool["name"] == "career.scan_and_review")
        properties = scan_tool["inputSchema"]["properties"]
        self.assertNotIn("useConfiguredSources", properties)
        self.assertNotIn("useCurrentCareerContext", properties)
        self.assertIn("poolMode", properties)
        self.assertIn("careerContext", properties)
        self.assertIn("mode", properties)
        self.assertIn("discovery", properties)
        self.assertIn("scanConfig", properties)
        discovery_properties = properties["discovery"]["properties"]
        self.assertIn("provider", discovery_properties)
        self.assertIn("providerRun", discovery_properties)
        candidate_schema = discovery_properties["candidates"]
        self.assertIn("Standardized results", candidate_schema["description"])
        candidate_properties = candidate_schema["items"]["properties"]
        for field in (
            "company",
            "role",
            "exactRole",
            "exact_role",
            "role_title",
            "location",
            "officialSource",
            "liveStatus",
            "qualificationFacts",
            "deadline",
            "applicationRule",
            "provenance",
            "uncertainty",
            "companyCoverageBucket",
            "company_coverage_bucket",
        ):
            self.assertIn(field, candidate_properties)
        self.assertIn(
            "MID_LARGE_TECH",
            candidate_properties["companyCoverageBucket"]["enum"],
        )
        self.assertIn(
            "FOREIGN_INTERNATIONAL_TEAM",
            candidate_properties["companyCoverageBucket"]["enum"],
        )
        compatibility = properties["scanConfig"]
        self.assertIn("Compatibility envelope", compatibility["description"])
        self.assertEqual(
            set(compatibility["properties"]), {"mode", "discovery"}
        )
        self.assertFalse(compatibility["additionalProperties"])
        pool_schema = properties["poolMode"]
        self.assertEqual(set(pool_schema["enum"]), {"BROAD", "FOCUSED"})
        mode_schema = properties["mode"]
        self.assertEqual(
            set(mode_schema["enum"]),
            {"configured_review", "market_discovery", "hybrid_discovery"},
        )

    def test_server_info_is_stateless_and_non_persistent(self):
        response = _mcp_post(
            self.port,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "career.server_info",
                    "arguments": {},
                },
            },
        )
        value = response["result"]["structuredContent"]
        self.assertEqual(value["version"], "0.2.10")
        self.assertTrue(value["stateless"])
        self.assertEqual(value["contextProvider"], "CALLER_SCOPED_OR_HOST_CONFIGURED_CONTEXT")
        self.assertFalse(value["contextPersistenceWrites"])
        self.assertFalse(value["application"])
        self.assertFalse(value["canonicalWrite"])
        self.assertEqual(
            value["discoveryModes"],
            ["configured_review", "market_discovery", "hybrid_discovery"],
        )
        self.assertEqual(
            value["genericDiscovery"]["provider"],
            "EXTERNAL_WEB_DISCOVERY_HANDOFF",
        )
        self.assertFalse(value["genericDiscovery"]["builtInWebDiscovery"])
        self.assertFalse(
            value["genericDiscovery"]["dedicatedAdaptersAreMarketBoundary"]
        )
        defaults = value["marketDiscoveryDefaults"]
        self.assertEqual(defaults["profileId"], "PUBLIC_NEUTRAL_MARKET_DISCOVERY_PROFILE")
        self.assertEqual(defaults["profileVersion"], "0.2.10")
        self.assertEqual(defaults["source"], "PUBLIC_NEUTRAL_DEFAULT")
        self.assertEqual(defaults["companySizePriority"], "NEUTRAL")
        self.assertEqual(defaults["bigTechPriority"], "NO_PRIORITY_BONUS")
        self.assertEqual(defaults["configuredAdapterPriority"], "NO_PRIORITY_BONUS")
        self.assertEqual(defaults["familiarBrandPriority"], "NO_PRIORITY_BONUS")
        self.assertEqual(defaults["decisionPriority"], [])
        self.assertEqual(defaults["locationOrdering"], [])
        self.assertEqual(defaults["coverageSafeguard"], "DISCOVERY_COVERAGE_IMBALANCE")

    def test_market_discovery_mode_uses_search_execution_handoff(self):
        response = _mcp_post(
            self.port,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "career.scan_and_review",
                    "arguments": {
                        "mode": "market_discovery",
                        "detailLevel": "review",
                        "discovery": {
                            "capabilityProfile": {"profile_ref": "SYNTHETIC-PROFILE"},
                            "roleHypotheses": [{
                                "id": "H1",
                                "role_or_family": "Product / Digital Product",
                                "capability_root_refs": ["cap-product"],
                                "search_terms": {
                                    "China": {"title": [{"term": "Product Manager", "why": "family variant"}]},
                                    "UK": {"title": [{"term": "Product Manager", "why": "family variant"}]},
                                    "Other": {"title": [{"term": "Product Manager", "why": "family variant"}]},
                                },
                            }],
                            "candidates": [{
                                "company": "Example Discovery Org",
                                "external_job_id": "DISC-1",
                                "role": "Product Manager",
                                "location": ["Example City Alpha"],
                                "role_family": "Product / Digital Product",
                                "ai_involvement": "NONE",
                                "evidence_refs": ["SYN-E1"],
                            }],
                        },
                    },
                },
            },
        )
        value = response["result"]["structuredContent"]
        self.assertEqual(value["mode"], "market_discovery")
        self.assertEqual(value["scan_config_source"], "DISCOVERY_INPUT")
        self.assertEqual(value["discovery"]["handoff_schema_version"], "0.2.4")
        self.assertEqual(value["pool_view"]["candidates"][0]["role_family"], "Product / Digital Product")
        self.assertEqual(value["pool_view"]["candidates"][0]["next_action"], "VERIFY_OFFICIAL_SOURCE")

    def test_market_discovery_without_candidates_returns_handoff(self):
        response = _mcp_post(
            self.port,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "career.scan_and_review",
                    "arguments": {
                        "mode": "market_discovery",
                        "detailLevel": "summary",
                        "discovery": {
                            "roleHypotheses": [{
                                "id": "H-HANDOFF",
                                "role_or_family": "Product / Digital Product",
                                "search_terms": {
                                    "China": {"title": [{"term": "Product Manager"}]},
                                },
                            }],
                        },
                    },
                },
            },
        )
        value = response["result"]["structuredContent"]
        self.assertEqual(value["mode"], "market_discovery")
        self.assertEqual(value["source_scope"]["sources"], [])
        self.assertEqual(value["discovery"]["state"], "HANDOFF_REQUIRED")
        self.assertEqual(
            value["discovery"]["generic_provider"]["provider"],
            "EXTERNAL_WEB_DISCOVERY_HANDOFF",
        )

    def test_scan_config_compatibility_envelope_ingests_two_candidates(self):
        discovery = {
            "provider": "EXTERNAL_WEB_DISCOVERY_HANDOFF",
            "providerRun": {
                "executor": "READ_ONLY_WEB",
                "observed_at": "2026-09-26",
            },
            "candidates": [
                {
                    "company": "Example Org Alpha",
                    "exactRole": "Product Manager",
                    "location": "Example City Alpha",
                    "officialSource": {
                        "url": "https://example.invalid/jobs/alpha",
                        "exact_role_verified": False,
                        "inspected_original": False,
                    },
                },
                {
                    "company": "Example Org Beta",
                    "exact_role": "Product Researcher",
                    "location": "Example City Beta",
                    "official_source": {
                        "url": "https://example.invalid/jobs/beta",
                        "exact_role_verified": False,
                        "inspected_original": False,
                    },
                },
            ],
        }
        callable_shapes = {
            "preferred": {
                "mode": "market_discovery",
                "discovery": discovery,
                "detailLevel": "summary",
            },
            "compatibility": {
                "scanConfig": {
                    "mode": "market_discovery",
                    "discovery": discovery,
                },
                "detailLevel": "summary",
            },
        }
        for offset, (shape, arguments) in enumerate(callable_shapes.items(), start=5):
            with self.subTest(shape=shape):
                response = _mcp_post(
                    self.port,
                    {
                        "jsonrpc": "2.0",
                        "id": offset,
                        "method": "tools/call",
                        "params": {
                            "name": "career.scan_and_review",
                            "arguments": arguments,
                        },
                    },
                )
                value = response["result"]["structuredContent"]
                self.assertEqual(value["mode"], "market_discovery")
                self.assertEqual(value["scan_config_source"], "DISCOVERY_INPUT")
                self.assertEqual(value["discovery"]["state"], "RESULTS_INGESTED")
                self.assertEqual(value["discovery"]["candidate_count"], 2)
                self.assertEqual(value["summary"]["discovery_candidate_count"], 2)
                self.assertEqual(len(value["pool_view"]["candidates"]), 2)
                for candidate in value["pool_view"]["candidates"]:
                    self.assertEqual(candidate["verification_status"], "NEEDS_VERIFY")
                    self.assertEqual(candidate["next_action"], "VERIFY_OFFICIAL_SOURCE")

    def test_market_discovery_coverage_imbalance_exposes_supplement_handoff(self):
        discovery = {
            "provider": "EXTERNAL_WEB_DISCOVERY_HANDOFF",
            "candidates": [
                {
                    "company": f"Example Head Tech {idx}",
                    "exactRole": f"Product Role {idx}",
                    "companyCoverageBucket": "LARGE_INTERNET_TECH",
                }
                for idx in range(4)
            ],
        }
        response = _mcp_post(
            self.port,
            {
                "jsonrpc": "2.0",
                "id": 20,
                "method": "tools/call",
                "params": {
                    "name": "career.scan_and_review",
                    "arguments": {
                        "mode": "market_discovery",
                        "discovery": discovery,
                        "detailLevel": "summary",
                    },
                },
            },
        )
        value = response["result"]["structuredContent"]
        self.assertEqual(value["discovery"]["state"], "RESULTS_INGESTED")
        self.assertEqual(
            value["discovery"]["coverage_state"],
            "DISCOVERY_COVERAGE_IMBALANCE",
        )
        self.assertEqual(
            value["discovery"]["continuation_state"], "SUPPLEMENT_REQUIRED"
        )
        supplement = value["discovery"]["supplemental_handoff"]
        self.assertEqual(supplement["trigger"], "DISCOVERY_COVERAGE_IMBALANCE")
        self.assertIn(
            "SAAS_ENTERPRISE_SOFTWARE", supplement["company_coverage_buckets"]
        )
        self.assertFalse(supplement["configured_adapters_are_market_boundary"])


if __name__ == "__main__":
    unittest.main()
