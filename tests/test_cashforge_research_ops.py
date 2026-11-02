import json
import sqlite3
import unittest

from cashforge_research_ops import init, remember_run, memory_for_topic, review_signals, validation_evidence


class ResearchOpsTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.row_factory=sqlite3.Row
        init(self.db)

    def tearDown(self):
        self.db.close()

    def test_memory_remembers_recurring_themes_across_runs(self):
        for run_id,score in [(1,42),(2,57)]:
            remember_run(self.db,{"run":{"id":run_id,"topic":"AI tools for shops","created_at":"2026-11-02"},
                "analysis":{"opportunities":[{"title":"Billing automation","score":{"score":score},"evidence_count":4,"keywords":["billing"]}]},
                "signals":[{"title":"Manual billing","source":"HN","url":"https://example.com"}]})
        memory=memory_for_topic(self.db,"AI tools for shops")
        self.assertEqual(len(memory["runs"]),2)
        self.assertEqual(memory["recurring_themes"][0]["seen_in_runs"],2)

    def test_sentiment_review_is_explicitly_heuristic(self):
        result=review_signals([{"title":"This tool is frustrating and broken","url":"https://example.com"}])
        self.assertEqual(result["totals"]["negative"],1)
        self.assertIn("keyword",result["method"])

    def test_validation_plan_does_not_claim_payment_proof(self):
        result=validation_evidence({},[{"title":"I pay $10 monthly","excerpt":"subscription price","url":"https://example.com"}])
        self.assertGreaterEqual(result["payment_language_records"],1)
        self.assertIn("not proof",result["warning"])


if __name__=="__main__":
    unittest.main()
