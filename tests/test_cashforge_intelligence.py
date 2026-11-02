import unittest

from cashforge_intelligence import group_evidence, run_analysis, build_markdown_report, build_html_report


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
        self.assertEqual(result["schema_version"], "cashforge-intelligence-v2")
        self.assertEqual(next(x["status"] for x in result["pipeline"] if x["id"] == "competitor_analysis"), "not_run")
        self.assertTrue(any("Competitor coverage was not assessed" in x for x in result["limitations"]))
        self.assertIn("idea", result["opportunities"][0])
        self.assertIn("skeptic_review", result["opportunities"][0])

    def test_grouped_examples_are_included_in_analysis(self):
        signals = [{
            "source": "HN", "title": "Manual invoice tools are expensive",
            "excerpt": "Billing takes too long", "url": "https://a.example/1",
            "match_count": 2,
            "match_examples": '[{"source":"Reddit","title":"Invoice billing takes too long","excerpt":"Manual invoice work is expensive","url":"https://b.example/2"}]'
        }]
        result = run_analysis("invoicing", "research", signals, 2)
        self.assertEqual(result["evidence"]["retained_records"], 2)

    def test_reports_are_generated(self):
        result = run_analysis("invoicing", "research", [], 0)
        run = {"created_at": "2026-11-02T00:00:00+00:00"}
        markdown = build_markdown_report(result, run)
        page = build_html_report(result, run)
        self.assertIn("# CashForge research report", markdown)
        self.assertIn("<!doctype html>", page.lower())
        self.assertIn("Research limitations", markdown)

    def test_rss_dates_are_counted_in_trend_history(self):
        signals = [
            {"source": "News", "title": "Small shop billing problems", "excerpt": "Manual work is slow", "url": "https://a.example/1", "published": "Mon, 02 Jun 2025 10:00:00 GMT"},
            {"source": "News", "title": "Small shop billing issues", "excerpt": "Manual work is frustrating", "url": "https://b.example/2", "published": "Wed, 02 Jul 2025 10:00:00 GMT"},
        ]
        result = run_analysis("billing", "research", signals, 2)
        self.assertEqual(result["trends"]["mentions_by_month"], {"2025-06": 1, "2025-07": 1})
        self.assertEqual(result["trends"]["month_over_month_change_pct"], 0.0)

    def test_empty_evidence_is_safe(self):
        result = run_analysis("topic", "objective", [], 0)
        self.assertEqual(result["opportunities"], [])
        self.assertEqual(result["decision"]["status"], "more_evidence_needed")


if __name__ == "__main__":
    unittest.main()
