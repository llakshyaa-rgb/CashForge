#!/usr/bin/env python3
"""CashForge local-first Trend Radar. Python standard library only."""
from __future__ import annotations
import difflib, html, json, os, re, sqlite3, time, threading, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from cashforge_intelligence import run_analysis, build_markdown_report, build_html_report
from cashforge_ai import chat as ai_chat, enrich_analysis, configured as ai_configured, AIUnavailable
from cashforge_competitors import discover as discover_competitors
from cashforge_monitor import init as init_monitors, create as create_monitor, list_all as list_monitors, set_enabled as set_monitor_enabled, due as due_monitors, mark_run as mark_monitor_run, compare_runs

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DB = DATA / "cashforge.db"
HOST = os.environ.get("CASHFORGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("CASHFORGE_PORT", "8766"))
UA = "CashForgeTrendRadar/0.1 (local research tool)"
MAX_RESULTS_PER_QUERY = 35
MAX_QUERY_ANGLES = 7

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
    cols={r[1] for r in db.execute('PRAGMA table_info(signals)')}
    if 'match_count' not in cols: db.execute('ALTER TABLE signals ADD COLUMN match_count INTEGER NOT NULL DEFAULT 1')
    if 'match_examples' not in cols: db.execute("ALTER TABLE signals ADD COLUMN match_examples TEXT NOT NULL DEFAULT '[]'")
    if 'selected_sources' not in {r[1] for r in db.execute('PRAGMA table_info(runs)')}:
        db.execute("ALTER TABLE runs ADD COLUMN selected_sources TEXT NOT NULL DEFAULT '[]'")
    init_monitors(db)
    db.execute("CREATE TABLE IF NOT EXISTS competitor_reports (run_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS ai_reports (run_id INTEGER PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)")
    db.commit()
    return db

def clean_text(value, limit=900):
    value=html.unescape(str(value or ''))
    value=re.sub(r'<[^>]+>', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()[:limit]

def build_queries(topic):
    angles=[topic, topic+' problems', topic+' alternatives', topic+' reviews', topic+' workflow', topic+' competitors pricing', topic+' complaints willingness to pay']
    seen=set(); result=[]
    for q in angles:
        if q.lower() not in seen: seen.add(q.lower()); result.append(q)
    return result[:MAX_QUERY_ANGLES]

def similarity(a,b):
    ta=set(re.findall(r'[a-z0-9]{3,}',a.lower()))
    tb=set(re.findall(r'[a-z0-9]{3,}',b.lower()))
    if not ta or not tb: return 0.0
    j=len(ta&tb)/len(ta|tb)
    seq=difflib.SequenceMatcher(None,a.lower(),b.lower()).ratio()
    return max(j,seq*0.82)

def request_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as res:
        return json.loads(res.read(2_000_000).decode("utf-8", "replace"))

def request_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=12) as res:
        return res.read(2_000_000).decode("utf-8", "replace")

def collect_hn(topic, queries=None):
    out=[]
    for q in (queries or [topic]):
        url="https://hn.algolia.com/api/v1/search?"+urllib.parse.urlencode({"query":q,"tags":"story","hitsPerPage":MAX_RESULTS_PER_QUERY})
        data=request_json(url)
        for x in data.get("hits",[]):
            link=x.get("url") or ("https://news.ycombinator.com/item?id="+str(x.get("objectID","")))
            out.append(dict(source="Hacker News",title=clean_text(x.get("title") or "Untitled",300),url=link,
              excerpt=clean_text(x.get("story_text") or "",900),author=clean_text(x.get("author") or "",100),
              published=x.get("created_at") or "",engagement=int(x.get("points") or 0)+int(x.get("num_comments") or 0)))
    return out

def collect_reddit(topic, queries=None):
    out=[]
    for q in (queries or [topic]):
        url="https://www.reddit.com/search.json?"+urllib.parse.urlencode({"q":q,"sort":"relevance","limit":50,"t":"year"})
        data=request_json(url)
        for wrap in data.get("data",{}).get("children",[]):
            x=wrap.get("data",{})
            out.append(dict(source="Reddit",title=clean_text(x.get("title") or "Untitled",300),
              url="https://www.reddit.com"+x.get("permalink",""),excerpt=clean_text(x.get("selftext") or "",900),
              author=clean_text(x.get("author") or "",100),published=datetime.fromtimestamp(x.get("created_utc",0),timezone.utc).isoformat(),
              engagement=int(x.get("score") or 0)+int(x.get("num_comments") or 0)))
    return out

def collect_news(topic, queries=None):
    out=[]
    for q in (queries or [topic]):
        url="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":q,"hl":"en-IN","gl":"IN","ceid":"IN:en"})
        root=ET.fromstring(request_text(url))
        for item in root.findall(".//item")[:MAX_RESULTS_PER_QUERY]:
            out.append(dict(source="Google News",title=clean_text(item.findtext("title") or "Untitled",300),
              url=(item.findtext("link") or "").strip(),excerpt=clean_text(item.findtext("description") or "",900),
              author="",published=item.findtext("pubDate") or "",engagement=0))
    return out

def cluster_signals(items):
    clusters=[]
    for item in sorted(items,key=lambda x:x.get("engagement",0),reverse=True):
        target=None
        for cluster in clusters:
            if similarity(item["title"],cluster[0]["title"]) >= 0.62:
                target=cluster
                break
        if target is None: clusters.append([item])
        else: target.append(item)
    return clusters

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
    queries=build_queries(topic)
    cur=db.execute("INSERT INTO runs(topic,objective,created_at,status,selected_sources) VALUES(?,?,?,?,?)",
                   (topic,objective,now,"collecting",json.dumps(sources)))
    run_id=cur.lastrowid
    collected=[]
    errors=[]
    for source in sources:
        if source not in collectors: continue
        try: collected.extend(collectors[source](topic,queries))
        except Exception as exc: errors.append(source+": "+str(exc)[:180])
    exact={}
    for item in collected:
        url=item.get("url","").strip()
        if not url.startswith(("http://","https://")): continue
        if url in exact: exact[url]["_exact_copies"]+=1
        else:
            item["_exact_copies"]=1
            exact[url]=item
    unique=list(exact.values())
    clusters=cluster_signals(unique)
    for cluster in clusters:
        representative=cluster[0]
        representative["score"]=score_signal(representative)
        examples=[{"source":x["source"],"title":x["title"],"url":x["url"],"excerpt":x["excerpt"][:300]} for x in cluster[1:]]
        match_count=sum(x["_exact_copies"] for x in cluster)
        db.execute("""INSERT OR IGNORE INTO signals(run_id,source,title,url,excerpt,author,published,engagement,score,match_count,match_examples)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
          (run_id,representative["source"],representative["title"],representative["url"],representative["excerpt"],
           representative["author"],representative["published"],representative["engagement"],representative["score"],
           match_count,json.dumps(examples)))
    summary=str(len(collected))+" raw records collected; "+str(len(unique))+" unique links; "+str(len(unique)-len(clusters))+" similar records grouped."
    if errors: summary += " Source issues: "+"; ".join(errors)
    db.execute("UPDATE runs SET status=?,source_count=?,signal_count=?,summary=? WHERE id=?",
      ("complete" if collected else "empty",len(set(x["source"] for x in unique)),len(clusters),summary,run_id))
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
    raw_records=sum(x["match_count"] for x in vals)
    def _examples(row):
        try:
            parsed=json.loads(row.get("match_examples") or "[]")
            return parsed if isinstance(parsed,list) else []
        except (ValueError,TypeError):
            return []
    unique_links=sum(1+len(_examples(x)) for x in vals)
    exact_duplicates=max(0,raw_records-unique_links)
    similar_records=max(0,unique_links-len(vals))
    analysis=run_analysis(run["topic"],run["objective"],vals,raw_records,
      [x.strip() for x in run["summary"].split("Source issues:",1)[1].split("; ") if x.strip()]
      if "Source issues:" in run["summary"] else [])
    analysis["evidence"].update({
      "unique_links":unique_links,
      "exact_url_duplicates":exact_duplicates,
      "similar_links_grouped":similar_records,
      "total_records_grouped":max(0,raw_records-len(vals)),
    })
    db.close()
    return {"run":dict(run),"signals":vals,"analysis":analysis,"metrics":{
      "sources":run["source_count"],"signals":len(vals),"raw_records":raw_records,
      "unique_links":unique_links,"exact_duplicates":exact_duplicates,
      "similar_records":similar_records,"grouped_records":max(0,raw_records-len(vals)),
      "clusters":sum(1 for x in vals if _examples(x)),
      "unique_domains":len(domains),"avg_priority":round(sum(x["score"] for x in vals)/len(vals),1) if vals else 0}}

def list_runs():
    db=connect()
    return [dict(x) for x in db.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 500")]

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
            parts=path.path.strip("/").split("/")
            try:
                rid=int(parts[2])
                data=get_run(rid)
            except (ValueError,IndexError):
                data=None
            if not data:
                return self.send(404,json.dumps({"error":"Run not found"}))
            if len(parts)==4 and parts[3] in {"report.md","report.html","report.json"}:
                if parts[3]=="report.md":
                    return self.send(200,build_markdown_report(data["analysis"],data["run"]),"text/markdown; charset=utf-8")
                if parts[3]=="report.html":
                    return self.send(200,build_html_report(data["analysis"],data["run"]),"text/html; charset=utf-8")
                return self.send(200,json.dumps(data,ensure_ascii=False,default=str))
            return self.send(200,json.dumps(data,ensure_ascii=False,default=str))
        elif path.path=="/api/ai/status": self.send(200,json.dumps({"configured":ai_configured(),"provider":"OpenRouter","model":os.environ.get("CASHFORGE_AI_MODEL","openai/gpt-oss-20b:free")}))
        elif path.path=="/api/monitors":
            db=connect(); self.send(200,json.dumps(list_monitors(db))); db.close()
        elif path.path.startswith("/api/compare/"):
            try: old_id,new_id=[int(x) for x in path.path.strip("/").split("/")[2:4]]
            except Exception: return self.send(400,json.dumps({"error":"Use /api/compare/OLD_ID/NEW_ID"}))
            old,new=get_run(old_id),get_run(new_id)
            if not old or not new: return self.send(404,json.dumps({"error":"One or both runs were not found"}))
            self.send(200,json.dumps(compare_runs(old,new),ensure_ascii=False))
        elif path.path.startswith("/api/run/") and path.path.endswith("/competitors"):
            try: rid=int(path.path.strip("/").split("/")[2])
            except (ValueError,IndexError): return self.send(400,json.dumps({"error":"Invalid run id"}))
            db=connect(); saved=db.execute("SELECT payload FROM competitor_reports WHERE run_id=?",(rid,)).fetchone(); db.close()
            if not saved: return self.send(404,json.dumps({"error":"No competitor report yet."}))
            self.send(200,saved["payload"])
        elif path.path=="/health": self.send(200,json.dumps({"ok":True,"app":"CashForge","database":str(DB.name),"ai_configured":ai_configured()}))
        else: self.send(404,json.dumps({"error":"Not found"}))
    def do_POST(self):
        try:
            size=int(self.headers.get("Content-Length","0"))
            if size>30000: return self.send(413,json.dumps({"error":"Request too large"}))
            payload=json.loads(self.rfile.read(size) or b"{}")
            if self.path=="/api/monitor":
                topic=str(payload.get("topic","")).strip()
                if len(topic)<3: return self.send(400,json.dumps({"error":"Enter a topic with at least 3 characters."}))
                db=connect(); mid=create_monitor(db,topic,payload.get("objective","Business opportunity discovery"),payload.get("sources",["Hacker News","Google News"]),payload.get("interval_hours",24)); db.close()
                return self.send(200,json.dumps({"id":mid,"status":"monitor_created"}))
            if self.path.startswith("/api/monitor/") and self.path.endswith("/toggle"):
                mid=int(self.path.strip("/").split("/")[3]); db=connect(); set_monitor_enabled(db,mid,payload.get("enabled",True)); db.close()
                return self.send(200,json.dumps({"status":"updated"}))
            if self.path.startswith("/api/run/") and self.path.endswith("/competitors"):
                rid=int(self.path.strip("/").split("/")[2]); data=get_run(rid)
                if not data: return self.send(404,json.dumps({"error":"Run not found"}))
                report=discover_competitors(data["run"]["topic"],data["signals"])
                db=connect(); db.execute("INSERT OR REPLACE INTO competitor_reports(run_id,payload,created_at) VALUES(?,?,?)",(rid,json.dumps(report,ensure_ascii=False),datetime.now(timezone.utc).isoformat())); db.commit(); db.close()
                return self.send(200,json.dumps(report,ensure_ascii=False))
            if self.path.startswith("/api/run/") and self.path.endswith("/ai-analysis"):
                rid=int(self.path.strip("/").split("/")[2]); data=get_run(rid)
                if not data: return self.send(404,json.dumps({"error":"Run not found"}))
                report=enrich_analysis(data["run"]["topic"],data["analysis"],data["signals"])
                db=connect(); db.execute("INSERT OR REPLACE INTO ai_reports(run_id,payload,created_at) VALUES(?,?,?)",(rid,json.dumps(report,ensure_ascii=False),datetime.now(timezone.utc).isoformat())); db.commit(); db.close()
                return self.send(200,json.dumps(report,ensure_ascii=False))
            if self.path.startswith("/api/run/") and self.path.endswith("/chat"):
                rid=int(self.path.strip("/").split("/")[2]); data=get_run(rid)
                if not data: return self.send(404,json.dumps({"error":"Run not found"}))
                messages=payload.get("messages",[])
                if not isinstance(messages,list) or not messages: return self.send(400,json.dumps({"error":"Send a message first."}))
                context={"topic":data["run"]["topic"],"analysis":data["analysis"],"evidence":data["signals"][:30]}
                return self.send(200,json.dumps(ai_chat(messages,context),ensure_ascii=False))
            if self.path!="/api/search": return self.send(404,json.dumps({"error":"Not found"}))
            data=run_research(payload)
            return self.send(200,json.dumps(data))
        except AIUnavailable as exc: return self.send(503,json.dumps({"error":str(exc),"ai_configured":ai_configured()}))
        except ValueError as exc: return self.send(400,json.dumps({"error":str(exc)}))
        except Exception as exc: return self.send(500,json.dumps({"error":"Research failed: "+str(exc)[:240]}))

def monitor_worker():
    while True:
        try:
            db=connect()
            for monitor in due_monitors(db):
                try:
                    data=run_research({"topic":monitor["topic"],"objective":monitor["objective"],
                                       "sources":json.loads(monitor["sources"])})
                    mark_monitor_run(db,monitor["id"],data["run"]["id"],monitor["interval_hours"])
                except Exception:
                    from datetime import timedelta
                    retry=(datetime.now(timezone.utc)+timedelta(hours=max(6,int(monitor["interval_hours"])))).isoformat()
                    db.execute("UPDATE monitors SET next_run_at=? WHERE id=?",(retry,monitor["id"]))
                    db.commit()
            db.close()
        except Exception:
            pass
        time.sleep(60)

if __name__=="__main__":
    connect().close()
    threading.Thread(target=monitor_worker,daemon=True).start()
    print(f"CashForge running at http://{HOST}:{PORT}")
    print("Local-only dashboard. Press Ctrl+C to stop.")
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
