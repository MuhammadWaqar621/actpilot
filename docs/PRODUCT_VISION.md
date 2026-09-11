# ActPilot — Product Vision

> Full original product concept, kept verbatim for reference. See [README.md](../README.md)
> for what's actually built and how to run it.

## The main idea

Think of the product as:

> **ChatGPT + Computer Vision + Browser Automation + AI Agent**

The AI has four capabilities: it can **understand** a page (DOM + vision), **answer** questions
about it, and **act** on it (browser tools), all driven by a single user request. The user doesn't
need to know whether a task requires AI reasoning, OCR, DOM parsing, or browser automation — they
just say what they want done, and the agent figures out how.

## Two primary capabilities

**A. Ask AI about the current page** — summarize, explain, extract, compare, "is this job
suitable for me", "convert this table to JSON", etc. The AI reads the DOM + screenshot and
answers via an LLM.

**B. Perform actions on the webpage** — click, fill forms, search, navigate, scroll, select,
upload, extract, compare pages, complete repetitive workflows. Example: "Fill this form using my
profile" → understand form → identify fields → retrieve user info → match fields → fill → verify
→ show result.

## Why both DOM and vision

DOM tells us structure (this is an input, a button, a dropdown). Vision tells us visual
relationships (this input is visually associated with the label "Expected Salary"). Combining
both gives much better page understanding than either alone.

## Agent design

- **Planner**: the LLM doesn't blindly control the browser — it produces a plan (e.g. for "fill
  this job application using my CV": understand JD → find form → identify fields → retrieve
  profile/CV → match → fill safe fields → generate answers where needed → upload CV → validate →
  stop before submission → ask for confirmation). LangGraph is a natural fit here.
- **Browser tool system**: a controlled set of tools (`browser.open`, `.click`, `.type`,
  `.select`, `.scroll`, `.screenshot`, `.extract`, `.find`, `.upload`, `.download`). The LLM emits
  a structured action (e.g. `{"action": "click", "target": {"selector": "#apply-button"}}`), the
  backend validates it, and only then does the extension execute it against the real browser.
- **Observe → Plan → Act → Observe loop**: more reliable than generating a whole action sequence
  in one shot. Each step re-observes the page before deciding the next action.
- **User memory**: a stored profile (name, contact info, education, experience, skills, CV,
  professional summary) so the agent doesn't need to ask for the same information every time.
- **RAG**: for larger unstructured user data (CV, portfolio, certificates, past answers), chunk +
  embed + store in a vector DB (Qdrant) and retrieve only what's relevant per request instead of
  stuffing everything into every prompt.
- **Computer vision**: OCR, layout understanding (header/sidebar/form/table/cards/charts), visual
  relationships between labels and fields, screenshot/graph/PDF understanding, and post-action
  visual verification (did the value actually get typed in?).

## Security model

Three permission levels:

- **Level 1 — Read**: read page, search, extract, screenshot. No confirmation needed.
- **Level 2 — Non-sensitive actions**: scroll, click, fill ordinary fields. No confirmation
  needed.
- **Level 3 — Sensitive actions**: submit, send email/message, purchase, delete, publish. Always
  require explicit user confirmation before executing.

## Example use cases

- **Job applications**: read JD → extract requirements → compare with CV → compute match % →
  explain missing skills → open application → fill fields → generate answers → upload CV → user
  reviews → user confirms → submit.
- **E-commerce**: "find the cheapest laptop with 32GB RAM and 1TB SSD" → search → extract products
  → filter/compare → return top 5 → "open the best one" → navigate → "add to cart" (asks for
  confirmation, since it's a consequential action).
- **Business data entry**: OCR an invoice → extract vendor/invoice #/date/amount/tax/items → open
  ERP → find the form → fill → verify → ask for confirmation before saving.

## Suggested target architecture

```text
actpilot/
├── extension/          # Chrome/Edge MV3 extension (chat UI, content script, background worker)
├── backend/             # FastAPI: auth, profile, agent API, LLM/vision/RAG services, tool
│                        # manager, action validator
├── database/            # PostgreSQL (users, profiles, task history)
└── docs/
```

Vector DB: Qdrant. Cache/task infra: Redis. Agent orchestration: LangGraph.

## MVP roadmap

This repo currently implements **MVP v1** only (see [README.md](../README.md)). The planned
progression:

1. **v1 (built)** — extension extracts page text + screenshot → FastAPI → Claude → answer
   questions about the current page. No actions yet.
2. **v2** — browser action tools (click, type, scroll, select, navigate) with an
   observe → plan → act → observe loop and a validator gate before execution.
3. **v3** — user profile + CV storage, RAG over unstructured documents, OCR/vision for
   screenshots and PDFs, so "fill this application using my CV" becomes possible.
4. **v4** — full agentic loop with verification and recovery (re-observe after each action,
   detect failures, retry or ask the user).
5. **v5** — specialized workflows on top of the general agent: job applications, research,
   data entry, e-commerce, CRM, invoices, QA testing.

## Competitive positioning

Not "our AI can understand screenshots" (commoditized). Instead: **"our AI can understand
webpages and execute tasks for you."** The moat is the combination — DOM understanding + computer
vision + LLM reasoning + agent planning + browser tools + memory/RAG + action verification +
human approval — not any single piece of it.
