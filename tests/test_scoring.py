import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer import (  # noqa: E402
    UseCase,
    assign_bucket,
    compute_score,
    score_breakdown,
    shared_layer_analysis,
)


class ScoringTests(unittest.TestCase):
    def make(self, **kw):
        base = dict(
            id="x",
            name="Test",
            description="",
            business_unit="BU",
            owner="Jane",
            data_sources=["public_data"],
            ai_type="RAG",
            risk_tier=1,
            value=5,
            feasibility=5,
            data_readiness=5,
            effort_weeks=4,
            human_in_loop=True,
            monitoring=True,
        )
        base.update(kw)
        return UseCase(**base)

    def test_quick_win_scores_high_and_lands_now(self):
        uc = self.make()
        uc.flags = uc.governance_gaps({"public_data"})
        uc.score = compute_score(uc)
        uc.bucket = assign_bucket(uc)
        self.assertGreaterEqual(uc.score, 70)
        self.assertEqual(uc.bucket, "Now")

    def test_high_risk_gaps_force_hold(self):
        uc = self.make(risk_tier=4, owner="TBD", human_in_loop=False, monitoring=False)
        uc.flags = uc.governance_gaps({"public_data"})
        uc.bucket = assign_bucket(uc)
        self.assertEqual(uc.bucket, "Hold")

    def test_unapproved_source_is_flagged(self):
        uc = self.make(data_sources=["mystery_tables"])
        gaps = uc.governance_gaps({"public_data"})
        self.assertTrue(any("unapproved data source" in g for g in gaps))

    def test_hold_overrides_high_score(self):
        uc = self.make(risk_tier=3, owner="TBD", monitoring=False)
        uc.flags = uc.governance_gaps({"public_data"})
        uc.score = compute_score(uc)
        uc.bucket = assign_bucket(uc)
        self.assertEqual(uc.bucket, "Hold")

    def test_score_breakdown_sums_to_score(self):
        uc = self.make()
        bd = score_breakdown(uc)
        self.assertAlmostEqual(round(sum(bd.values()), 1), compute_score(uc), places=1)
        self.assertIn("value", bd)
        self.assertIn("effort", bd)

    def test_shared_entity_detected_across_cases(self):
        a = self.make(id="a", required_entities=["customer", "document"])
        b = self.make(id="b", required_entities=["customer", "policy"])
        c = self.make(id="c", required_entities=["transaction"])
        shared = shared_layer_analysis([a, b, c], {})
        self.assertEqual(len(shared["entity_to_cases"]["customer"]), 2)
        self.assertGreater(len(shared["chosen"]), 0)
        self.assertGreaterEqual(shared["coverage"], 0.0)


if __name__ == "__main__":
    unittest.main()
