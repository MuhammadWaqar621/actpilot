# ActPilot

An AI browser agent: a Chrome/Edge extension that reads the page you're on (DOM text + a
screenshot) and answers questions about it via Claude, in a chat side panel.

This repo currently implements **MVP v1** — ask-only, no page actions yet. See
[docs/PRODUCT_VISION.md](docs/PRODUCT_VISION.md) for the full product concept and the roadmap
toward an agent that can also *act* on pages (fill forms, click, navigate, RAG over your CV,
vision-based verification, etc).

## How it works

```text
Extension (side panel)
  ├─ content script  → extracts page URL/title/visible text
  ├─ background       → captures a screenshot of the visible tab
  └─ sidebar chat UI  → sends {question, page text, screenshot} to the backend
                              │
                              ▼
                     FastAPI backend (/api/analyze)
                              │
                              ▼
                        Claude (Anthropic API)
                              │
                              ▼
                      Answer shown in chat
```

## Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
copy .env.example .env        # Windows: copy, macOS/Linux: cp
```

Edit `.env` and set `ANTHROPIC_API_KEY` to a key from https://console.anthropic.com/.

Run it:

```bash
uvicorn app.main:app --reload --port 8000
```

Check it's up: `GET http://localhost:8000/api/health` → `{"status": "ok"}`

## Extension setup

No build step needed — it's plain JS/HTML/CSS.

1. Open `chrome://extensions` (or `edge://extensions`)
2. Enable **Developer mode**
3. Click **Load unpacked** and select the `extension/` folder
4. Click the ActPilot toolbar icon to open the side panel on any page
5. If your backend isn't on `http://localhost:8000`, click the ⚙ icon in the panel and set the
   correct backend URL

Ask it things like "Summarize this page" or "What are the requirements in this job posting?".

## Project layout

```text
actpilot/
├── backend/
│   └── app/
│       ├── main.py        # FastAPI app + CORS
│       ├── api/            # routes + request/response schemas
│       ├── llm/             # Claude client
│       └── core/            # settings
├── extension/
│   ├── manifest.json        # MV3, side panel + content script + background worker
│   └── src/
│       ├── background/      # service worker (screenshot capture, opens side panel)
│       ├── content/         # extracts page text from the DOM
│       └── sidebar/         # chat UI
└── docs/
    └── PRODUCT_VISION.md    # full product concept + phased roadmap
```

## Notes

- `CORS_ALLOW_ORIGINS=*` in `.env` is fine for local development only — restrict it before
  shipping anything beyond your own machine.
- The backend never executes actions against the page in this version — it only reads and
  answers. Action tools (click/type/fill) are the next milestone; see the roadmap in
  [docs/PRODUCT_VISION.md](docs/PRODUCT_VISION.md).
