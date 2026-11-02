"""CashForge fieldwork: consent-based interviews, opt-in demand leads, competitor profiles and retrieval."""
import json, re, sqlite3
from datetime import datetime, timezone

def init(db):
    db.execute("CREATE TABLE IF NOT EXISTS interview_projects(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id INTEGER NOT NULL,title TEXT NOT NULL,consent_text TEXT NOT NULL,questions_json TEXT NOT NULL,created_at TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS interview_notes(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id INTEGER NOT NULL,participant_code TEXT NOT NULL,consented INTEGER NOT NULL,notes TEXT NOT NULL,created_at TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS demand_leads(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id INTEGER NOT NULL,contact_label TEXT NOT NULL,contact_method TEXT NOT NULL,consented INTEGER NOT NULL,price_test TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'interested',notes TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS competitor_profiles(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id INTEGER NOT NULL,name TEXT NOT NULL,domain TEXT NOT NULL,source_url TEXT NOT NULL,pricing_notes TEXT NOT NULL DEFAULT '',feature_notes TEXT NOT NULL DEFAULT '',customer_notes TEXT NOT NULL DEFAULT '',verification_status TEXT NOT NULL DEFAULT 'unverified',updated_at TEXT NOT NULL,UNIQUE(run_id,domain))")
    db.commit()

def interview_kit(topic, analysis):
    return {"title":"Customer discovery · "+topic,
      "consent_text":"I am researching this problem, not selling anything during this conversation. Participation is voluntary. You may skip any question or stop at any time. Notes will be anonymous unless you explicitly agree otherwise. May I take notes, and do you agree to participate?",
      "questions":["Tell me about the last time you experienced this problem. What happened?","How do you handle it today? Walk me through the last real example.","How often has this happened in the last 30 days?","What did it cost in time, money or missed sales?","What have you already tried? Why did you stop or continue?","Have you paid for a workaround? What did you actually pay, and when?","Who else chooses or pays for a solution?","What would make you reject a proposed solution?","May I contact you once for a follow-up? Only if you explicitly opt in."],
      "hypotheses_to_test":[x.get("title","") for x in analysis.get("opportunities",[])[:5]],
      "rules":["Ask about past behaviour, not hypothetical enthusiasm.","Do not lead participants.","Do not collect sensitive personal data.","Do not retain contact details without explicit permission."]}

def create_interview_project(db, run_id, topic, analysis):
    kit=interview_kit(topic,analysis)
    cur=db.execute("INSERT INTO interview_projects(run_id,title,consent_text,questions_json,created_at) VALUES(?,?,?,?,?)",(run_id,kit["title"],kit["consent_text"],json.dumps(kit["questions"]),datetime.now(timezone.utc).isoformat()))
    db.commit()
    return {"id":cur.lastrowid,**kit}

def save_interview_note(db, project_id, participant_code, consented, notes):
    if not consented: raise ValueError("Notes cannot be saved without recorded consent.")
    code=re.sub(r"[^A-Za-z0-9_-]","",str(participant_code))[:40]
    note=str(notes).strip()
    if not code or not note or len(note)>6000: raise ValueError("Use an anonymous code and notes of 1–6000 characters.")
    cur=db.execute("INSERT INTO interview_notes(project_id,participant_code,consented,notes,created_at) VALUES(?,?,?,?,?)",(int(project_id),code,1,note,datetime.now(timezone.utc).isoformat()))
    db.commit()
    return cur.lastrowid

def save_demand_lead(db, run_id, label, method, consented, price_test, notes=""):
    if not consented: raise ValueError("Do not store a contact or follow-up lead without explicit opt-in.")
    if not str(label).strip() or not str(method).strip(): raise ValueError("Add an anonymous label and permitted contact method.")
    cur=db.execute("INSERT INTO demand_leads(run_id,contact_label,contact_method,consented,price_test,status,notes,created_at) VALUES(?,?,?,?,?,'interested',?,?)",(int(run_id),str(label)[:80],str(method)[:120],1,str(price_test)[:300],str(notes)[:1200],datetime.now(timezone.utc).isoformat()))
    db.commit()
    return cur.lastrowid

def save_competitor_profile(db, run_id, name, url, pricing="", features="", customer="", verified=False):
    import urllib.parse
    p=urllib.parse.urlparse(str(url))
    if p.scheme!="https" or not p.hostname: raise ValueError("Competitor profile needs a public HTTPS source URL.")
    db.execute("INSERT INTO competitor_profiles(run_id,name,domain,source_url,pricing_notes,feature_notes,customer_notes,verification_status,updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(run_id,domain) DO UPDATE SET name=excluded.name,source_url=excluded.source_url,pricing_notes=excluded.pricing_notes,feature_notes=excluded.feature_notes,customer_notes=excluded.customer_notes,verification_status=excluded.verification_status,updated_at=excluded.updated_at",(int(run_id),str(name)[:160],p.hostname.lower(),url,str(pricing)[:1000],str(features)[:1000],str(customer)[:1000],"human_verified" if verified else "unverified",datetime.now(timezone.utc).isoformat()))
    db.commit()

def list_competitors(db, run_id):
    init(db)
    return [dict(x) for x in db.execute("SELECT * FROM competitor_profiles WHERE run_id=? ORDER BY domain",(int(run_id),))]

def semantic_retrieve(query, records, limit=8):
    if not records: return {"matches":[],"method":"empty"}
    texts=[str(x.get("title",""))+" "+str(x.get("excerpt","")) for x in records[:100]]
    try:
        from cashforge_ai import embeddings
        vectors=embeddings([query]+texts)
        q=vectors[0]; scored=[]
        for row,vec in zip(records,texts and vectors[1:]):
            dot=sum(a*b for a,b in zip(q,vec)); na=sum(a*a for a in q)**.5; nb=sum(b*b for b in vec)**.5
            scored.append((dot/(na*nb) if na and nb else 0,row))
        method="provider embeddings"
    except Exception:
        q=set(re.findall(r"[a-z0-9]{3,}",query.lower())); scored=[]
        for row,txt in zip(records,texts):
            words=set(re.findall(r"[a-z0-9]{3,}",txt.lower()))
            scored.append((len(q&words)/len(q|words) if q|words else 0,row))
        method="local lexical fallback"
    scored.sort(key=lambda x:x[0],reverse=True)
    return {"method":method,"matches":[{"score":round(score,4),"evidence":row} for score,row in scored[:max(1,min(20,int(limit)))]]}
