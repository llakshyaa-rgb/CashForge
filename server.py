#!/usr/bin/env python3
"""CashForge local-first Trend Radar. Python standard library only."""
from __future__ import annotations
import json, os, re, sqlite3, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DB = DATA / "cashforge.db"
HOST = os.environ.get("CASHFORGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("CASHFORGE_PORT", "8766"))
UA = "CashForgeTrendRadar/0.1 (local research tool)"
MAX_RESULTS = 25

def connect():
    DATA.mkdir(exist_ok=True)
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, objective TEXT NOT NULL,
      created_at TEXT NOT NULL, status TEXT NOT NULL, source_count INTEGER NOT NULL DEFAULT 0,
      signal_count INTEGER NOT NULL DEFAULT 0, summary TEXT NOT NULL DEFAULT ''
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS signals (
      id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL, source TEXT NOT NULL,
      title TEXT NOT NULL, url TEXT NOT NULL, excerpt TEXT NOT NULL DEFAULT '',
      author TEXT NOT NULL DEFAULT '', published TEXT NOT NULL DEFAULT '',
      engagement INTEGER NOT NULL DEFAULT 0, score REAL NOT NULL DEFAULT 0,
      FOREIGN KEY(run_id) REFERENCES runs(id), UNIQUE(run_id,url)
    )""")
    db.commit()
    return db

def request_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as res:
        return json.loads(res.read(2_000_000).decode("utf-8", "replace"))

def request_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=12) as res:
        return res.read(2_000_000).decode("utf-8", "replace")

def collect_hn(topic):
    url = "https://hn.algolia.com/api/v1/search?"+urllib.parse.urlencode({"query":topic,"tags":"story","hitsPerPage":MAX_RESULTS})
    data = request_json(url)
    out=[]
    for x in data.get("hits",[]):
        link=x.get("url") or ("https://news.ycombinator.com/item?id="+str(x.get("objectID","")))
        out.append(dict(source="Hacker News",title=x.get("title") or "Untitled",url=link,
          excerpt=(x.get("story_text") or "")[:600],author=x.get("author") or "",
          published=x.get("created_at") or "",engagement=int(x.get("points") or 0)+int(x.get("num_comments") or 0)))
    return out

def collect_reddit(topic):
    url="https://www.reddit.com/search.json?"+urllib.parse.urlencode({"q":topic,"sort":"relevance","limit":MAX_RESULTS,"t":"year"})
    data=request_json(url)
    out=[]
    for wrap in data.get("data",{}).get("children",[]):
        x=wrap.get("data",{})
        out.append(dict(source="Reddit",title=x.get("title") or "Untitled",
          url="https://www.reddit.com"+x.get("permalink",""),excerpt=(x.get("selftext") or "")[:600],
          author=x.get("author") or "",published=datetime.fromtimestamp(x.get("created_utc",0),timezone.utc).isoformat(),
          engagement=int(x.get("score") or 0)+int(x.get("num_comments") or 0)))
    return out

def collect_news(topic):
    url="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":topic,"hl":"en-IN","gl":"IN","ceid":"IN:en"})
    root=ET.fromstring(request_text(url))
    out=[]
    for item in root.findall(".//item")[:MAX_RESULTS]:
        out.append(dict(source="Google News",title=item.findtext("title") or "Untitled",
          url=item.findtext("link") or "",excerpt=(item.findtext("description") or "")[:600],
          author="",published=item.findtext("pubDate") or "",engagement=0))
    return out

def score_signal(item):
    # Ranking aid only; raw engagement is not comparable across platforms.
    title=(item["title"]+" "+item["excerpt"]).lower()
    topic_words=set(re.findall(r"[a-z0-9]{3,}", title))
    return round(min(100, 18 + min(item["engagement"],80)*0.55 + min(len(topic_words),30)*0.7),1)

def run_research(payload):
    topic=str(payload.get("topic","")).strip()[:160]
    objective=str(payload.get("objective","Business opportunity discovery"))[:80]
    sources=payload.get("sources",["Hacker News","Reddit","Google News"])
    if len(topic)<3: raise ValueError("Enter a topic with at least 3 characters.")
    collectors={"Hacker News":collect_hn,"Reddit":collect_reddit,"Google News":collect_news}
    db=connect()
    now=datetime.now(timezone.utc).isoformat()
    cur=db.execute("INSERT INTO runs(topic,objective,created_at,status) VALUES(?,?,?,?)",(topic,objective,now,"collecting"))
    run_id=cur.lastrowid
    collected=[]; errors=[]
    for source in sources:
        if source not in collectors: continue
        try:
            collected.extend(collectors[source](topic))
        except Exception as exc:
            errors.append(source+": "+str(exc)[:180])
    unique={}
    for item in collected:
        url=item.get("url","").strip()
        if url and url not in unique: unique[url]=item
    items=list(unique.values())
    for item in items:
        item["score"]=score_signal(item)
        db.execute("""INSERT OR IGNORE INTO signals(run_id,source,title,url,excerpt,author,published,engagement,score)
          VALUES(?,?,?,?,?,?,?,?,?)""",(run_id,item["source"],item["title"],item["url"],item["excerpt"],item["author"],item["published"],item["engagement"],item["score"]))
    summary=f"{len(items)} unique public results from {len(set(x['source'] for x in items))} source(s)."
    if errors: summary += " Some sources failed: "+"; ".join(errors)
    status="complete" if items else "empty"
    db.execute("UPDATE runs SET status=?,source_count=?,signal_count=?,summary=? WHERE id=?",
      (status,len(set(x["source"] for x in items)),len(items),summary,run_id))
    db.commit()
    return get_run(run_id)

def get_run(run_id):
    db=connect()
    run=db.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
    if not run: return None
    signals=db.execute("SELECT * FROM signals WHERE run_id=? ORDER BY score DESC, engagement DESC",(run_id,)).fetchall()
    vals=[dict(x) for x in signals]
    domains={}
    for x in vals:
        host=urllib.parse.urlparse(x["url"]).netloc.lower().removeprefix("www.")
        domains[host]=domains.get(host,0)+1
    return {"run":dict(run),"signals":vals,"metrics":{
      "sources":run["source_count"],"signals":run["signal_count"],
      "unique_domains":len(domains),"avg_priority":round(sum(x["score"] for x in vals)/len(vals),1) if vals else 0}}

def list_runs():
    db=connect()
    return [dict(x) for x in db.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 40")]

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,code,body,ctype="application/json; charset=utf-8"):
        raw=body if isinstance(body,bytes) else body.encode()
        self.send_response(code); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        path=urllib.parse.urlparse(self.path)
        if path.path=="/":
            try: self.send(200,(ROOT/"index.html").read_bytes(),"text/html; charset=utf-8")
            except OSError: self.send(500,"Dashboard file missing","text/plain")
        elif path.path=="/api/runs": self.send(200,json.dumps(list_runs()))
        elif path.path.startswith("/api/run/"):
            try: rid=int(path.path.rsplit("/",1)[1]); data=get_run(rid)
            except ValueError: data=None
            self.send(200 if data else 404,json.dumps(data or {"error":"Run not found"}))
        elif path.path=="/health": self.send(200,json.dumps({"ok":True,"app":"CashForge","database":str(DB.name)}))
        else: self.send(404,json.dumps({"error":"Not found"}))
    def do_POST(self):
        if self.path!="/api/search": return self.send(404,json.dumps({"error":"Not found"}))
        try:
            size=int(self.headers.get("Content-Length","0"))
            if size>20000: return self.send(413,json.dumps({"error":"Request too large"}))
            payload=json.loads(self.rfile.read(size) or b"{}")
            data=run_research(payload)
            self.send(200,json.dumps(data))
        except ValueError as exc: self.send(400,json.dumps({"error":str(exc)}))
        except Exception as exc: self.send(500,json.dumps({"error":"Research failed: "+str(exc)[:240]}))

if __name__=="__main__":
    connect().close()
    print(f"CashForge running at http://{HOST}:{PORT}")
    print("Local-only dashboard. Press Ctrl+C to stop.")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
