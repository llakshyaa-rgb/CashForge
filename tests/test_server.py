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

    def test_topic_is_required(self):
        with self.assertRaises(ValueError):
            server.run_research({"topic":"  ","sources":[]})

if __name__=="__main__":
    unittest.main()
