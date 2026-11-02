"""Optional OpenRouter-backed analyst and embeddings for CashForge.

No key is stored in the database or browser. Configure OPENROUTER_API_KEY in
the shell environment. Local analysis remains available without credentials.
"""
from __future__ import annotations
import json, os, urllib.request, urllib.error

API = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = os.environ.get("CASHFORGE_AI_MODEL", "openai/gpt-oss-20b:free")
DEFAULT_EMBED_MODEL = os.environ.get("CASHFORGE_EMBED_MODEL", "openai/text-embedding-3-small")

class AIUnavailable(RuntimeError):
    pass

def configured():
    return bool(os.environ.get("OPENROUTER_API_KEY"))

def _post(path, payload, timeout=75):
    key=os.environ.get("OPENROUTER_API_KEY","").strip()
    if not key:
        raise AIUnavailable("AI is not configured. Set OPENROUTER_API_KEY in Termux, then restart CashForge.")
    body=json.dumps(payload).encode()
    req=urllib.request.Request(API+path,data=body,headers={
        "Authorization":"Bearer "+key,"Content-Type":"application/json",
        "HTTP-Referer":"http://127.0.0.1:8766","X-Title":"CashForge"
    })
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            return json.loads(response.read(4_000_000).decode("utf-8","replace"))
    except urllib.error.HTTPError as exc:
        detail=exc.read(1200).decode("utf-8","replace")
        raise AIUnavailable("AI provider returned HTTP "+str(exc.code)+": "+detail) from exc
    except Exception as exc:
        raise AIUnavailable("AI provider request failed: "+str(exc)[:300]) from exc

def chat(messages, context=None, model=None):
    system=("You are CashForge's skeptical market-research analyst. Use only supplied evidence. "
            "Cite evidence using [E1], [E2] identifiers when available. Separate observed facts, "
            "inferences and unknowns. Never invent market size, competitor facts, pricing, quotes, "
            "demand, revenue or source citations. Explicitly say when evidence is insufficient. "
            "Give practical validation experiments and counterarguments.")
    if context:
        system += "\n\nCURRENT RESEARCH CONTEXT:\n"+json.dumps(context,ensure_ascii=False)[:24000]
    payload={"model":model or DEFAULT_MODEL,"temperature":0.2,
             "messages":[{"role":"system","content":system}]+messages[-16:]}
    data=_post("/chat/completions",payload)
    return {"text":data["choices"][0]["message"]["content"],
            "model":data.get("model",model or DEFAULT_MODEL),
            "usage":data.get("usage",{})}

def enrich_analysis(topic, analysis, signals, model=None):
    evidence=[]
    for i,row in enumerate(signals[:45],1):
        evidence.append({"id":"E"+str(i),"source":row.get("source"),"title":row.get("title"),
                         "excerpt":row.get("excerpt","")[:450],"url":row.get("url")})
    prompt=("Analyze this research snapshot. Return a concise structured report with: "
            "executive_summary, strongest_pain_points, competitor_questions_to_investigate, "
            "market_gap_hypotheses, customer_segments, willingness_to_pay_evidence, "
            "counterarguments, validation_plan, unknowns. Do not claim competitors were verified "
            "unless evidence explicitly identifies them. Every factual claim must cite E IDs.\n\n"
            +json.dumps({"topic":topic,"local_analysis":analysis,"evidence":evidence},ensure_ascii=False)[:26000])
    result=chat([{"role":"user","content":prompt}],model=model)
    return result

def embeddings(texts, model=None):
    data=_post("/embeddings",{"model":model or DEFAULT_EMBED_MODEL,
                              "input":[str(x)[:4000] for x in texts[:64]]},timeout=90)
    return [x["embedding"] for x in sorted(data.get("data",[]),key=lambda x:x.get("index",0))]
