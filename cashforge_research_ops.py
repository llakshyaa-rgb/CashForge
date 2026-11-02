"""CashForge research operations: cross-run memory, page verification and validation evidence.

Read-only, bounded collection. All extracted commercial details are leads requiring human review.
"""
from __future__ import annotations
import html, ipaddress, json, re, socket, sqlite3, urllib.parse, urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

UA="CashForgeResearch/1.0 (local read-only market research)"

def init(db):
    db.execute("""CREATE TABLE IF NOT EXISTS research_memory(
      id INTEGER PRIMARY KEY AUTOINCREMENT, topic_key TEXT NOT NULL, topic TEXT NOT NULL,
      run_id INTEGER NOT NULL, created_at TEXT NOT NULL, themes_json TEXT NOT NULL,
      signals_json TEXT NOT NULL, UNIQUE(topic_key,run_id))""")
    db.execute("""CREATE TABLE IF NOT EXISTS validation_reviews(
      run_id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)""")
    db.commit()

def _key(s):
    return " ".join(re.findall(r"[a-z0-9]+",str(s or "").lower()))

def remember_run(db, run):
    init(db)
    topic=run.get("run",{}).get("topic","")
    key=_key(topic)
    analysis=run.get("analysis",{})
    themes=[{"title":x.get("title",""),"score":x.get("score",{}).get("score",0),
             "evidence_count":x.get("evidence_count",0),"keywords":x.get("keywords",[])}
            for x in analysis.get("opportunities",[])[:30]]
    signals=[{"title":x.get("title",""),"source":x.get("source",""),"url":x.get("url","")}
             for x in run.get("signals",[])[:60]]
    db.execute("INSERT OR IGNORE INTO research_memory(topic_key,topic,run_id,created_at,themes_json,signals_json) VALUES(?,?,?,?,?,?)",
       (key,topic,run.get("run",{}).get("id"),run.get("run",{}).get("created_at") or datetime.now(timezone.utc).isoformat(),
        json.dumps(themes),json.dumps(signals)))
    db.commit()

def memory_for_topic(db, topic, limit=12):
    init(db); key=_key(topic)
    rows=db.execute("SELECT * FROM research_memory WHERE topic_key=? ORDER BY id DESC LIMIT ?",
                    (key,max(1,min(40,int(limit))))).fetchall()
    history=[{"run_id":r["run_id"],"created_at":r["created_at"],"themes":json.loads(r["themes_json"]),
              "signals":json.loads(r["signals_json"])} for r in rows]
    counts={}
    for h in history:
        for t in h["themes"]:
            k=_key(t["title"])
            if not k: continue
            item=counts.setdefault(k,{"title":t["title"],"seen_in_runs":0,"latest_score":t["score"],"latest_run_id":h["run_id"]})
            item["seen_in_runs"]+=1
    return {"topic":topic,"runs":history,"recurring_themes":sorted(counts.values(),key=lambda x:(x["seen_in_runs"],x["latest_score"]),reverse=True),
            "note":"Historical recurrence is not proof of market demand; scan coverage may change."}

class _Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in {"script","style","noscript","svg","nav","footer","header"}: self.skip+=1
        if tag in {"meta"}:
            d=dict(attrs)
            if d.get("name","").lower() in {"description"} or d.get("property","").lower() in {"og:description"}:
                self.parts.append(d.get("content",""))
    def handle_endtag(self,tag):
        if tag in {"script","style","noscript","svg","nav","footer","header"} and self.skip: self.skip-=1
    def handle_data(self,data):
        if not self.skip: self.parts.append(data)

def _safe_url(url):
    p=urllib.parse.urlparse(str(url or ""))
    if p.scheme!="https" or not p.hostname or p.username or p.password: return False
    try:
        infos=socket.getaddrinfo(p.hostname,None)
        return bool(infos) and all(ipaddress.ip_address(x[4][0]).is_global for x in infos)
    except Exception: return False

def inspect_pages(records, limit=12):
    results=[]
    seen=set()
    for row in records[:80]:
        url=str(row.get("url",""))
        host=urllib.parse.urlparse(url).hostname or ""
        if not host or host in seen: continue
        seen.add(host)
        if not _safe_url(url):
            results.append({"domain":host,"url":url,"status":"skipped","reason":"Only public HTTPS pages are inspected."})
            continue
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html"})
            with urllib.request.urlopen(req,timeout=10) as res:
                final=res.geturl()
                if not _safe_url(final): raise ValueError("Redirect destination was not a public HTTPS address.")
                ctype=res.headers.get("Content-Type","")
                if "html" not in ctype.lower(): raise ValueError("Page is not HTML.")
                raw=res.read(350_000).decode("utf-8","replace")
            parser=_Text(); parser.feed(raw)
            text=re.sub(r"\s+"," "," ".join(parser.parts)).strip()
            low=text.lower()
            prices=sorted(set(re.findall(r"(?:[$₹€£]\s?\d[\d,.]*(?:\s?\/\s?(?:mo|month|year|yr))?|\d[\d,.]*\s?(?:usd|inr)\s?(?:per month|monthly|annually))",text,re.I)))[:12]
            feature_terms=["pricing","features","integrations","free trial","enterprise"," API ","automation","analytics","security","support","mobile app"]
            features=[term.strip() for term in feature_terms if term.lower() in low]
            title=re.search(r"<title[^>]*>(.*?)</title>",raw,re.I|re.S)
            results.append({"domain":host,"url":final,"status":"inspected","title":html.unescape(re.sub("<[^>]+>","",title.group(1))).strip()[:180] if title else row.get("title",""),
                "pricing_mentions":prices,"feature_page_signals":features,"excerpt":text[:900],"page_text":text[:30000],
                "caveat":"Extracted page text is not a verified pricing/feature statement; inspect the source manually."})
        except Exception as exc:
            results.append({"domain":host,"url":url,"status":"failed","reason":str(exc)[:180]})
        if len(results)>=max(1,min(20,int(limit))): break
    return {"pages":results,"inspected":sum(x["status"]=="inspected" for x in results),
            "limitations":["Only a small sample of public HTTPS pages is fetched.","Page text and price-like strings can be misleading or stale.","No claim is made that a company is a direct competitor without human review."]}

def review_signals(signals):
    positive={"love","great","excellent","easy","helpful","works","recommend","solved","useful","amazing"}
    negative={"hate","broken","bad","terrible","frustrating","expensive","slow","bug","bugs","failed","difficult","annoying","unreliable"}
    rows=[]; totals={"positive":0,"negative":0,"mixed":0,"neutral":0}
    for s in signals[:500]:
        words=set(re.findall(r"[a-z]{3,}",(str(s.get("title",""))+" "+str(s.get("excerpt",""))).lower()))
        p=len(words&positive); n=len(words&negative)
        label="mixed" if p and n else "positive" if p else "negative" if n else "neutral"
        totals[label]+=1
        rows.append({"source":s.get("source"),"title":s.get("title"),"url":s.get("url"),"sentiment_hint":label,
                     "matched_terms":sorted(words&(positive|negative))})
    return {"totals":totals,"items":rows[:120],
            "method":"Transparent keyword hints, not a trained sentiment model. Sarcasm and context are not understood.",
            "note":"Use original posts for qualitative review; sentiment counts are directional only."}

def validation_evidence(analysis, signals):
    evidence=[]
    for i,s in enumerate(signals[:100],1):
        txt=(str(s.get("title",""))+" "+str(s.get("excerpt",""))).lower()
        if re.search(r"\b(pay|paid|paying|subscription|pricing|price|budget|cost|buy|purchase|revenue)\b",txt):
            evidence.append({"id":"P"+str(i),"source":s.get("source"),"title":s.get("title"),"url":s.get("url"),
                             "excerpt":str(s.get("excerpt",""))[:300]})
    return {"payment_language_records":len(evidence),"evidence":evidence[:30],
      "experiments":[
        {"name":"Problem interviews","method":"Interview 5–8 people who match the observed audience; ask about their last real incident and current workaround.","success_signal":"Repeated recent incidents and a costly workaround, not polite interest."},
        {"name":"Concierge pilot","method":"Offer a manual, opt-in solution to 3–5 target users before building automation.","success_signal":"Users complete the workflow repeatedly and request continued access."},
        {"name":"Price commitment","method":"Show a clearly priced pilot or preorder with honest delivery terms; collect no money until legally and operationally ready.","success_signal":"A concrete commitment at a stated price, not likes or survey intent."},
        {"name":"Retention test","method":"Track repeat use over 2–4 weeks and ask why users stop.","success_signal":"Users return without repeated prompting and can name measurable value."}],
      "warning":"Keyword mentions of payment are not proof anyone paid for this proposed product."}
