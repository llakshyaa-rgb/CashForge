# CashForge

CashForge is a private-first, mobile-friendly opportunity research workspace. The first module is an evidence-led Trend Radar: collect public signals, review source links, compare supporting and opposing evidence, and save research runs locally.

## Current scope

- Local web dashboard designed for phone screens.
- Python standard-library server; no npm, database service, or paid hosting required.
- Public-source discovery from Hacker News Algolia, Reddit's public JSON endpoints, and Google News RSS.
- SQLite research library preserving past topics, objectives, selected source combinations, and results across refreshes.
- Multi-angle topic discovery and grouped near-duplicate reporting, with representative links to inspect matching mentions.
- Transparent heuristic scoring for discussion heat and evidence coverage.
- Source-level inspection, filters, export, and repeatable topic studies.
- Clear distinction between observed signals and hypotheses.

This is the first CashForge module, not an automated money-making or revenue-prediction system. It does not create products, publish content, spend money, or guarantee demand or income. Collection is read-only and bounded; respect source terms, rate limits, and applicable law.

## Run locally (Termux / Linux / macOS)

```bash
git clone https://github.com/llakshyaa-rgb/CashForge.git
cd CashForge
python server.py
```

CashForge uses port `8766` by default (Purffle can keep using `8765`). Open `http://127.0.0.1:8766` on the same device. Keep the terminal session running. No API key is required for the built-in public-source collectors.

## How it works

1. Enter a topic and select a research objective.
2. CashForge searches up to five related query angles per selected source, with bounded requests (up to 35 Hacker News / Google News items per angle and up to 50 Reddit items per angle, subject to source limits).
3. Exact URL duplicates and title-similar records are grouped rather than silently discarded; counts and representative links remain visible. All research runs are stored in a local SQLite database.
4. Each signal retains its original URL, source, timestamp, and available engagement metadata.
5. The dashboard shows observed discussion, source diversity, and a provisional evidence score. Scores are prioritization aids, not verified market demand.
6. Open each source and decide what to validate next.

## Privacy and safety

- Research data and saved research configurations stay in `data/cashforge.db` on the device.
- Refreshing opens a fresh blank research screen; use the Research Library to reopen previous runs.
- The server binds to loopback by default; it is not exposed to the public internet.
- No cookies, account passwords, browser sessions, or tokens are collected.
- Do not commit your local database or private research exports.
- Stop collection if a source blocks access or signals rate limiting.

## Project status

The Trend Radar is the first working foundation. More CashForge modules (competitor analysis, product packaging, distribution, monetization, and performance feedback) are intentionally not included yet.

## Inspiration and attribution

The evidence-first workflow is informed by the MIT-licensed [Trend Opportunity Radar](https://github.com/datou202307-design/trend-opportunity-radar). CashForge is an independent implementation with its own UI, local storage, and collectors; it is not an official fork or affiliated product.
