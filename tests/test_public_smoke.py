import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class PublicFixtureSmokeTest(unittest.TestCase):
    def test_demo_is_synthetic_and_non_actionable(self):
        job = json.loads((ROOT / "tests/fixtures/public-demo-job.json").read_text())
        trace = json.loads((ROOT / "tests/outputs/public-demo-trace.json").read_text())
        self.assertTrue(job["role_key"].startswith("SYNTHETIC:"))
        self.assertEqual(job["source_level"], "SYNTHETIC")
        self.assertTrue(job["official_job_id"].startswith("SYN-"))
        self.assertFalse(trace["external_action"])
        self.assertTrue(trace["human_review_required"])

if __name__ == "__main__":
    unittest.main()
