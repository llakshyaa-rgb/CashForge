"""Bounded competitor discovery using public search endpoints only."""
from __future__ import annotations
import json, urllib.parse, urllib.request, re
from datetime import datetime, timezone

UA="CashForgeCompetitorResearch/1.0 (local read-only research)"
def _get(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json, application/rss+xml, application/xml"})
    with urllib.request.urlopen(req,timeout=15) as r:
        return r.read(1_500_000).decode("utf-8","replace")

def discover(topic, evidence, limit=30):
    # Extract named products/brands from explicit competitor/alternative discussions,
    # then query public HN + Google News for verifiable source links.
    seed=[]
    for row in evidence[:80]:
        text=(str(row.get("title",""))+" "+str(row.get("excerpt",""))).strip()
        if re.search(r"\b(competitor|alternative|instead of|replaced|switch from|compared to)\b",text,re.I):
            seed.append({"source":row.get("source"),"title":row.get("title"),"url":row.get("url"),
                         "excerpt":row.get("excerpt","")[:350]})
    queries=[topic+" competitors",topic+" alternatives pricing",topic+" product comparison reviews"]
    results=[]
    for q in queries:
        try:
            url="https://hn.algolia.com/api/v1/search?"+urllib.parse.urlencode({"query":q,"tags":"story","hitsPerPage":12})
            data=json.loads(_get(url))
            for hit in data.get("hits",[]):
                link=hit.get("url") or ("https://news.ycombinator.com/item?id="+str(hit.get("objectID","")))
                results.append({"source":"Hacker News","title":hit.get("title",""),"url":link,
                                "excerpt":(hit.get("story_text") or "")[:500],"published":hit.get("created_at","")})
        except Exception as exc:
            results.append({"source":"Hacker News","error":str(exc)[:180]})
        try:
            rss="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":q,"hl":"en-IN","gl":"IN","ceid":"IN:en"})
            raw=_get(rss)
            import xml.etree.ElementTree as ET
            root=ET.fromstring(raw)
            for item in root.findall(".//item")[:10]:
                results.append({"source":"Google News","title":item.findtext("title",""),
                                "url":item.findtext("link",""),"excerpt":re.sub("<[^>]+>"," ",item.findtext("description","")),
                                "published":item.findtext("pubDate","")})
        except Exception as exc:
            results.append({"source":"Google News","error":str(exc)[:180]})
    unique={}
    for row in results:
        if row.get("url","").startswith("http"):
            unique[row["url"]]=row
    return {"status":"partial" if any(x.get("error") for x in results) else "collected",
            "seed_mentions":seed[:20],"records":list(unique.values())[:limit],
            "queries":queries,"limitations":[
                "Search results are discovery leads, not a verified competitor directory.",
                "Pricing and feature claims require opening and checking each original page.",
                "No competitor or market gap is confirmed from name mentions alone."
            ]}
