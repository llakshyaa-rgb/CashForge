import sqlite3, unittest
from cashforge_fieldwork import init, create_interview_project, save_interview_note, save_demand_lead, save_competitor_profile, list_competitors, semantic_retrieve

class FieldworkTests(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(":memory:"); self.db.row_factory=sqlite3.Row; init(self.db)
 def tearDown(self): self.db.close()
 def test_interview_notes_require_consent(self):
  p=create_interview_project(self.db,1,"shop billing",{"opportunities":[]})
  with self.assertRaises(ValueError): save_interview_note(self.db,p["id"],"P1",False,"notes")
  self.assertTrue(save_interview_note(self.db,p["id"],"P1",True,"Past incident details"))
 def test_demand_leads_require_opt_in(self):
  with self.assertRaises(ValueError): save_demand_lead(self.db,1,"P1","email",False,"₹100/mo")
  self.assertTrue(save_demand_lead(self.db,1,"P1","email",True,"₹100/mo"))
 def test_competitor_profiles_are_source_linked(self):
  save_competitor_profile(self.db,1,"Example","https://example.com/pricing",pricing="₹99/mo",verified=True)
  self.assertEqual(list_competitors(self.db,1)[0]["verification_status"],"human_verified")
 def test_retrieval_has_local_fallback(self):
  result=semantic_retrieve("billing automation", [{"title":"Billing automation","excerpt":"invoice workflow"}])
  self.assertEqual(len(result["matches"]),1)
if __name__=="__main__": unittest.main()
