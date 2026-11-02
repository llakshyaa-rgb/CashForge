import unittest
import server

class CashForgeTests(unittest.TestCase):
    def test_score_is_bounded(self):
        item={"title":"AI support tools","excerpt":"small business customer service","engagement":100000}
        self.assertGreaterEqual(server.score_signal(item),0)
        self.assertLessEqual(server.score_signal(item),100)

    def test_database_initializes(self):
        db=server.connect()
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        db.close()
        self.assertIn("runs",tables)
        self.assertIn("signals",tables)

    def test_query_angles_expand(self):
        queries=server.build_queries("AI trackers")
        self.assertGreaterEqual(len(queries),3)
        self.assertEqual(queries[0],"AI trackers")

    def test_html_is_cleaned(self):
        self.assertEqual(server.clean_text("<b>AI tracker</b> &amp; tools"),"AI tracker & tools")

    def test_similar_titles_are_grouped_not_lost(self):
        items=[
            {"title":"AI tracker for small businesses","engagement":10},
            {"title":"AI tracker tools for small business","engagement":5},
            {"title":"Gardening tips for beginners","engagement":2},
        ]
        groups=server.cluster_signals(items)
        self.assertEqual(sum(len(group) for group in groups),3)
        self.assertLess(len(groups),3)

    def test_topic_is_required(self):
        with self.assertRaises(ValueError):
            server.run_research({"topic":"  ","sources":[]})

if __name__=="__main__":
    unittest.main()
