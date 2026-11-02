import unittest

from cashforge_intelligence import group_evidence, run_analysis


class IntelligenceTests(unittest.TestCase):
    def test_related_evidence_is_grouped_and_preserved(self):
        items = [
            {"source": "HN", "title": "Expensive invoicing software for freelancers", "excerpt": "Manual billing is frustrating", "url": "https://a.example/1"},
            {"source": "Reddit", "title": "Freelancer invoicing software is expensive", "excerpt": "Manual billing is frustrating", "url": "https://b.example/2"},
            {"source": "News", "title": "Beginner gardening tips", "excerpt": "Plant tomatoes in spring", "url": "https://c.example/3"},
        ]
        groups = group_evidence(items)
        self.assertEqual(sum(group["size"] for group in groups), 3)
        self.assertLess(len(groups), 3)

    def test_analysis_discloses_competitor_limit(self):
        signals = [
            {"source": "HN", "title": "Expensive invoicing is frustrating", "excerpt": "Manual billing takes hours", "url": "https://a.example/1", "match_examples": "[]"},
            {"source": "Reddit", "title": "Invoicing software is expensive", "excerpt": "Manual billing is a problem", "url": "https://b.example/2", "match_examples": "[]"},
            {"source": "HN", "title": "Manual invoicing tools cost too much", "excerpt": "I would pay for a better tool", "url": "https://a.example/3", "match_examples": "[]"},
        ]
        result = run_analysis("invoicing", "opportunity discovery", signals, 3)
        self.assertEqual(result["schema_version"], "cashforge-analysis-v1")
        self.assertEqual(result["pipeline"][-2]["status"], "not_run")
        self.assertTrue(any("Competitor coverage is not assessed" in x for x in result["limitations"]))

    def test_empty_evidence_is_safe(self):
        result = run_analysis("topic", "objective", [], 0)
        self.assertEqual(result["opportunities"], [])
        self.assertEqual(result["decision"]["status"], "more_evidence_needed")


if __name__ == "__main__":
    unittest.main()
