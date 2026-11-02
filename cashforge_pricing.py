"""Extract structured, source-linked competitor pricing clues from public page text."""
import re
from datetime import datetime, timezone

CURRENCY={
 "$":"USD","US$":"USD","USD":"USD","₹":"INR","INR":"INR","€":"EUR","EUR":"EUR","£":"GBP","GBP":"GBP","A$":"AUD","C$":"CAD"
}
PRICE_RE=re.compile(r"(?P<currency>US\$|A\$|C\$|USD|INR|GBP|EUR|AUD|CAD|[$₹€£])\s*(?P<amount>\d[\d,]*(?:\.\d{1,2})?)\s*(?P<period>/(?:month|mo|year|yr|week|wk)|per\s+(?:month|year|week)|monthly|annually|yearly)?",re.I)

def extract_prices(text):
    found=[]; seen=set()
    for m in PRICE_RE.finditer(str(text or "")[:30000]):
        raw=m.group(0).strip()
        currency=m.group("currency").upper()
        code=CURRENCY.get(currency,currency)
        period=(m.group("period") or "").lower().replace("per ","/")
        if period in {"/mo","monthly"}: billing="monthly"
        elif period in {"/month"}: billing="monthly"
        elif period in {"/yr","/year","annually","yearly"}: billing="annual"
        elif period in {"/week","/wk"}: billing="weekly"
        else: billing="unspecified"
        try: amount=float(m.group("amount").replace(",",""))
        except ValueError: continue
        key=(code,amount,billing)
        if key in seen: continue
        seen.add(key)
        start=max(0,m.start()-90); end=min(len(text),m.end()+90)
        found.append({"display":raw,"currency":code,"amount":amount,"billing":billing,
          "context":re.sub(r"\s+"," ",str(text)[start:end]).strip()})
        if len(found)>=30: break
    return found

def build_price_intelligence(page_report):
    rows=[]
    for page in page_report.get("pages",[]):
        if page.get("status")!="inspected": continue
        text=page.get("page_text") or page.get("excerpt","")
        prices=extract_prices(text)
        rows.append({"competitor_domain":page.get("domain"),"page_title":page.get("title"),
          "source_url":page.get("url"),"prices":prices,
          "pricing_page_hint":bool(re.search(r"pricing|plans|subscription",str(page.get("url",""))+" "+str(page.get("title","")),re.I)),
          "checked_at":datetime.now(timezone.utc).isoformat(),
          "verification":"unverified_extracted_text",
          "warning":"Price-like text only. Confirm currency, billing period, plan availability, taxes, region and current price on the original page."})
    return {"competitors":rows,"price_count":sum(len(x["prices"]) for x in rows),
      "limitations":["Only prices present in the fetched page excerpt are detected.","JavaScript-rendered pricing, login-gated plans and region-specific prices may be missed.","Amounts without a billing period remain unspecified; no currency conversion or price inference is performed."]}

def integration_package(run, price_intelligence=None, competitor_report=None):
    return {"schema_version":"cashforge.orbit.research.v1",
      "producer":{"name":"CashForge","role":"market_research_and_opportunity_intelligence"},
      "created_at":run.get("run",{}).get("created_at"),
      "research":{"run_id":run.get("run",{}).get("id"),"topic":run.get("run",{}).get("topic"),
        "objective":run.get("run",{}).get("objective"),"summary":run.get("run",{}).get("summary"),
        "metrics":run.get("metrics",{}),"opportunities":run.get("analysis",{}).get("opportunities",[]),
        "risks":run.get("analysis",{}).get("risks",[]),"evidence":run.get("signals",[])[:120]},
      "competitor_discovery":competitor_report or {},
      "competitor_price_intelligence":price_intelligence or {},
      "handoff_to_orbit":{"recommended_tasks":["Conduct consent-based customer interviews","Validate observed pain with target users","Execute approved experiments and workflows"],
        "note":"CashForge supplies research and hypotheses. Orbit owns outreach, interviews and execution. No demand or purchase is asserted by this package."}}
