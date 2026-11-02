"""Persistent monitoring metadata and scan-to-scan comparisons."""
from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone

def init(db):
    db.execute("""CREATE TABLE IF NOT EXISTS monitors(
      id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, objective TEXT NOT NULL,
      sources TEXT NOT NULL, interval_hours INTEGER NOT NULL DEFAULT 24,
      enabled INTEGER NOT NULL DEFAULT 1, last_run_id INTEGER, next_run_at TEXT,
      created_at TEXT NOT NULL)""")
    db.commit()

def create(db, topic, objective, sources, interval_hours=24):
    interval=max(6,min(168,int(interval_hours)))
    now=datetime.now(timezone.utc)
    cur=db.execute("INSERT INTO monitors(topic,objective,sources,interval_hours,enabled,next_run_at,created_at) VALUES(?,?,?,?,1,?,?)",
      (topic[:160],objective[:80],json.dumps(sources),interval,now.isoformat(),now.isoformat()))
    db.commit()
    return cur.lastrowid

def list_all(db):
    init(db)
    return [dict(x) for x in db.execute("SELECT * FROM monitors ORDER BY id DESC")]

def set_enabled(db, monitor_id, enabled):
    init(db)
    db.execute("UPDATE monitors SET enabled=? WHERE id=?",(1 if enabled else 0,int(monitor_id)))
    db.commit()

def due(db):
    init(db)
    now=datetime.now(timezone.utc).isoformat()
    return [dict(x) for x in db.execute("SELECT * FROM monitors WHERE enabled=1 AND (next_run_at IS NULL OR next_run_at<=?)",(now,))]

def mark_run(db, monitor_id, run_id, interval_hours):
    from datetime import timedelta
    now=datetime.now(timezone.utc)
    nxt=now+timedelta(hours=max(6,min(168,int(interval_hours))))
    db.execute("UPDATE monitors SET last_run_id=?,next_run_at=? WHERE id=?",(run_id,nxt.isoformat(),monitor_id))
    db.commit()

def compare_runs(old, new):
    def themes(data):
        return {x.get("title","").lower():x for x in data.get("analysis",{}).get("opportunities",[])}
    a,b=themes(old),themes(new)
    return {"new_themes":[b[k] for k in b.keys()-a.keys()],
            "fading_themes":[a[k] for k in a.keys()-b.keys()],
            "persistent_themes":[{"before":a[k],"after":b[k]} for k in a.keys()&b.keys()],
            "signal_delta":new.get("metrics",{}).get("signals",0)-old.get("metrics",{}).get("signals",0),
            "note":"Comparison of collected snapshots, not a forecast. Source coverage and query changes can affect counts."}
