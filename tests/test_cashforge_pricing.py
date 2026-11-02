import unittest
from cashforge_pricing import extract_prices, build_price_intelligence, integration_package

class PricingTests(unittest.TestCase):
    def test_extracts_currency_and_billing(self):
        rows=extract_prices("Starter $12/month, Pro ₹999 annually and Enterprise €49/year")
        self.assertEqual([(x["currency"],x["billing"]) for x in rows],
                         [("USD","monthly"),("INR","annual"),("EUR","annual")])

    def test_does_not_invent_billing_period(self):
        rows=extract_prices("Plan costs $25")
        self.assertEqual(rows[0]["billing"],"unspecified")

    def test_builds_unverified_price_rows(self):
        result=build_price_intelligence({"pages":[{"status":"inspected","domain":"example.com",
          "title":"Pricing","url":"https://example.com/pricing","page_text":"Basic $10/month"}]})
        self.assertEqual(result["price_count"],1)
        self.assertEqual(result["competitors"][0]["verification"],"unverified_extracted_text")

    def test_orbit_contract_version_and_handoff(self):
        run={"run":{"id":7,"topic":"test","objective":"research","created_at":"now"},
             "analysis":{"opportunities":[],"risks":[]},"signals":[],"metrics":{}}
        package=integration_package(run)
        self.assertEqual(package["schema_version"],"cashforge.orbit.research.v1")
        self.assertIn("Conduct consent-based customer interviews",
                      package["handoff_to_orbit"]["recommended_tasks"])
        self.assertNotIn("api_key",str(package).lower())

if __name__ == "__main__":
    unittest.main()
