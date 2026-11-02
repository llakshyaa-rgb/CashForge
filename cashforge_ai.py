"""Optional provider-backed AI for CashForge. Secrets stay in ignored local data/."""
from __future__ import annotations
import json, os, urllib.request, urllib.error
from pathlib import Path

DATA_DIR=Path(__file__).resolve().parent/"data"
SETTINGS_FILE=DATA_DIR/"provider_settings.json"
DEFAULTS={"provider":"openrouter","base_url":"https://openrouter.ai/api/v1",
          "model":"openai/gpt-oss-20b:free","embedding_model":"openai/text-embedding-3-small"}

class AIUnavailable(RuntimeError):
    pass

def read_settings():
    data=dict(DEFAULTS)
    try:
        saved=json.loads(SETTINGS_FILE.read_text("utf-8"))
        if isinstance(saved,dict): data.update({k:v for k,v in saved.items() if k in {"provider","base_url","model","embedding_model","api_key"}})
    except (OSError,ValueError,TypeError):
        pass
    if not data.get("api_key") and os.environ.get("OPENROUTER_API_KEY"):
        data.update(provider="openrouter",base_url="https://openrouter.ai/api/v1",
                    model=os.environ.get("CASHFORGE_AI_MODEL",DEFAULTS["model"]),
                    embedding_model=os.environ.get("CASHFORGE_EMBED_MODEL",DEFAULTS["embedding_model"]),
                    api_key=os.environ["OPENROUTER_API_KEY"])
    return data

def save_settings(payload):
    provider=str(payload.get("provider","openrouter")).lower()
    if provider not in {"openrouter","openai"}: raise ValueError("Choose OpenRouter or OpenAI.")
    key=str(payload.get("api_key","")).strip()
    if not key: raise ValueError("Paste an API key.")
    base=("https://openrouter.ai/api/v1" if provider=="openrouter" else "https://api.openai.com/v1")
    model=str(payload.get("model") or (DEFAULTS["model"] if provider=="openrouter" else "gpt-4o-mini")).strip()[:160]
    embed=str(payload.get("embedding_model") or ("openai/text-embedding-3-small" if provider=="openrouter" else "text-embedding-3-small")).strip()[:160]
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps({"provider":provider,"base_url":base,"model":model,
                                         "embedding_model":embed,"api_key":key}),encoding="utf-8")
    try: SETTINGS_FILE.chmod(0o600)
    except OSError: pass
    return {"provider":provider,"model":model,"embedding_model":embed,"configured":True}

def clear_settings():
    try: SETTINGS_FILE.unlink()
    except FileNotFoundError: pass

def configured():
    return bool(read_settings().get("api_key"))

def public_settings():
    s=read_settings()
    return {"provider":s.get("provider","openrouter"),"model":s.get("model"),
            "embedding_model":s.get("embedding_model"),"configured":bool(s.get("api_key")),
            "key_saved":bool(s.get("api_key"))}

def _post(path,payload,timeout=75):
    settings=read_settings()
    key=str(settings.get("api_key","")).strip()
    if not key: raise AIUnavailable("No AI provider key saved. Open Settings and add one.")
    base=str(settings.get("base_url","https://openrouter.ai/api/v1")).rstrip("/")
    headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"}
    if settings.get("provider")=="openrouter":
        headers.update({"HTTP-Referer":"http://127.0.0.1:8766","X-Title":"CashForge"})
    req=urllib.request.Request(base+path,data=json.dumps(payload).encode(),headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            return json.loads(response.read(4_000_000).decode("utf-8","replace"))
    except urllib.error.HTTPError as exc:
        detail=exc.read(1200).decode("utf-8","replace")
        raise AIUnavailable("AI provider returned HTTP "+str(exc.code)+": "+detail) from exc
    except Exception as exc:
        raise AIUnavailable("AI provider request failed: "+str(exc)[:300]) from exc

def chat(messages,context=None,model=None):
    settings=read_settings()
    system=("You are CashForge's skeptical market-research analyst. Use only supplied evidence. "
            "Cite evidence using [E1], [E2] identifiers when available. Separate observed facts, "
            "inferences and unknowns. Never invent market size, competitor facts, pricing, quotes, "
            "demand, revenue or source citations. Explicitly say when evidence is insufficient. "
            "Give practical validation experiments and counterarguments.")
    if context: system+="\n\nCURRENT RESEARCH CONTEXT:\n"+json.dumps(context,ensure_ascii=False)[:24000]
    payload={"model":model or settings.get("model") or DEFAULTS["model"],"temperature":0.2,
             "messages":[{"role":"system","content":system}]+messages[-16:]}
    data=_post("/chat/completions",payload)
    return {"text":data["choices"][0]["message"]["content"],
            "model":data.get("model",payload["model"]),"usage":data.get("usage",{})}

def enrich_analysis(topic,analysis,signals,model=None):
    evidence=[{"id":"E"+str(i),"source":row.get("source"),"title":row.get("title"),
               "excerpt":row.get("excerpt","")[:450],"url":row.get("url")}
              for i,row in enumerate(signals[:45],1)]
    prompt=("Analyze this research snapshot. Return a concise structured report with executive_summary, "
            "strongest_pain_points, competitor_questions_to_investigate, market_gap_hypotheses, "
            "customer_segments, willingness_to_pay_evidence, counterarguments, validation_plan, unknowns. "
            "Do not claim competitors were verified unless evidence explicitly identifies them. "
            "Every factual claim must cite E IDs.\n\n"+
            json.dumps({"topic":topic,"local_analysis":analysis,"evidence":evidence},ensure_ascii=False)[:26000])
    return chat([{"role":"user","content":prompt}],model=model)

def embeddings(texts,model=None):
    settings=read_settings()
    selected=model or settings.get("embedding_model") or DEFAULTS["embedding_model"]
    data=_post("/embeddings",{"model":selected,"input":[str(x)[:4000] for x in texts[:64]]},timeout=90)
    return [x["embedding"] for x in sorted(data.get("data",[]),key=lambda x:x.get("index",0))]
