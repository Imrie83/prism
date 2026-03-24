# Shinrai Prism Audit

**Internal prospecting tool for [Shinrai Web](https://imrie83.github.io/shinrai/) — find Japanese businesses with weak English websites and reach out with a personalised, bilingual email.**

Prism scans a Japanese website, takes a screenshot, runs it through an AI vision model, and produces a scored audit report covering translation quality, visual hierarchy, UX patterns, and localisation issues. From any scan result you can generate and send a polished bilingual outreach email with an embedded Japanese-language report card — all without leaving the app.

---

## Screenshots

> **Scan Page** — paste a URL, choose a scan mode, watch it run
>
> ![Scan Page](docs/screenshot-scan.png)

> **Results Page** — score ring, issue cards, severity breakdown, screenshot lightbox
>
> ![Results Page](docs/screenshot-results.png)

> **Email Drawer** — generated bilingual email with embedded report card, preview before sending
>
> ![Email Drawer](docs/screenshot-email.png)

---

## Features

- **Three scan modes**
  - **Shallow** — single page, top 8 issues displayed, fast. Summary and issues returned in Japanese (client-facing).
  - **Deep** — crawls up to N pages, full 20-issue report, English (internal use).
  - **Batch** — run shallow scans across multiple URLs in sequence.
- **AI vision analysis** — screenshot + HTML sent together; catches both text and visual/layout issues
- **Scored report** — 0-100 English-readiness score with severity breakdown (high / medium / low)
- **Bilingual email generation** — Japanese (Keigo) + English sections, embedded report card, CTA buttons
- **One-click send** — Gmail SMTP via app password, sent directly from the tool
- **Switchable AI providers** — Ollama (local), OpenAI, or Anthropic Claude; separate models for audit vs email
- **Scan history** — three independent history banks (shallow / deep / batch), removable runs
- **Dark / light theme**, token cost tracking, Test Connection button

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Browser / UI                     │
│               React + Vite  (port 5174)             │
└──────────────────────────┬──────────────────────────┘
                           │ /api/*
┌──────────────────────────▼──────────────────────────┐
│              Python FastAPI backend                 │
│                   (port 8000)                       │
│                                                     │
│  • /api/analyze      — run scan                     │
│  • /api/generate-email — write email                │
│  • /api/send-email   — send via Gmail SMTP          │
│  • /api/cancel/:id   — cancel running scan          │
│  • /api/test-ai      — cheap connectivity check     │
└──────────┬─────────────────────────────┬────────────┘
           │                             │
┌──────────▼──────────┐   ┌──────────────▼────────────┐
│  Screenshot service │   │        AI provider        │
│  Node + Playwright  │   │  Ollama / OpenAI / Claude │
│     (port 3000)     │   |                           |
└─────────────────────┘   └───────────────────────────┘
```

---

## Requirements

- [Docker](https://www.docker.com/) + Docker Compose v2
- One of:
  - **Ollama** running locally (recommended for free use)
  - **OpenAI** API key
  - **Anthropic** API key
- A **Gmail account** with an [App Password](https://myaccount.google.com/apppasswords) for sending email (2FA must be enabled)

---

## Quick Start (Docker — recommended)

```bash
# 1. Clone the repo
git clone https://github.com/yourname/prism.git
cd prism

# 2. Build and start all services
docker compose up --build -d

# 3. Open the app
open http://localhost:5174
```

That's it. The frontend, backend, and screenshot service all start together.

> ⚠️ **After any code change** you must rebuild — `docker compose restart` does **not** pick up new code:
> ```bash
> docker compose up --build -d
> # or:
> make build
> ```

### Makefile shortcuts

```bash
make build        # rebuild and start
make up           # start without rebuilding
make down         # stop everything
make logs         # tail all service logs
make logs-backend # tail backend only
make ps           # show running containers
```

---

## Running Locally (without Docker)

Useful during development. You need Node.js 18+ and Python 3.12+.

### 1. Screenshot service

```bash
cd screenshot-service
npm install
npm run dev
# Runs on http://localhost:3000
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8000 --timeout-keep-alive 120
# Runs on http://localhost:8000
```

### 3. Frontend

```bash
npm install
npm run dev
# Runs on http://localhost:5174
```

Run each in a separate terminal. The Vite dev server proxies `/api/*` to `localhost:8000` automatically.

---

## AI Provider Setup

Configure everything in the **Settings** panel (gear icon). Changes are saved to localStorage.

### Option A — Ollama (local, free)

Best for privacy and cost. Requires a model with vision support.

```bash
# Install Ollama: https://ollama.com
ollama pull llava          # vision model for audits
ollama pull mistral        # or any model for email generation
ollama serve               # starts on http://localhost:11434
```

In Settings:
- **Audit provider**: Ollama
- **Ollama base URL**: `http://localhost:11434` (default)
- **Ollama model**: `llava` (or any vision-capable model)

> When running via Docker, Ollama on your host machine is reached automatically via `host.docker.internal:11434`. No extra config needed.

Recommended models:

| Use | Model |
|-----|-------|
| Audit (vision) | `qwen2.5vl:7b`, `llava:13b`, `minicpm-v` |
| Email writing | `qwen2.5:14b`, `mistral`, `llama3.1` |

### Option B — OpenAI

```
Audit model:  gpt-4o          (vision required)
Email model:  gpt-4o-mini     (cheaper, plenty good)
```

In Settings → set provider to **OpenAI** and paste your API key.

### Option C — Anthropic Claude (recommended for quality)

```
Audit model:  claude-haiku-4-5-20251001   (fast, cheap, excellent vision)
Email model:  claude-sonnet-4-6            (best writing quality)
```

In Settings → set provider to **Claude** and paste your API key. The app uses separate model selectors for audit vs email so you can use Haiku for scanning and Sonnet for writing.

---

## Email Setup (Gmail)

1. Enable **2-Step Verification** on your Google account
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Create a password for "Mail" → copy the 16-character code
4. In Prism Settings → Email section:
   - **Gmail address**: your full Gmail address
   - **App password**: the 16-character code (no spaces)
   - Fill in your name, title, and website — these appear in the signature

---

## Scan Modes Explained

| Mode | Pages | Issues shown | Summary language | Use for |
|------|-------|-------------|-----------------|---------|
| **Shallow** | 1 | Top 8 (of all found) | Japanese | Quick prospecting, batch runs |
| **Deep** | Up to N (configurable) | Top 20 | English | Internal research before outreach |
| **Batch** | 1 per URL | Top 8 | Japanese | Processing a list of prospects |

Shallow and Batch scans return Japanese-language summaries and issue explanations directly — these feed straight into the client-facing report card without a translation step. Deep scans are English-first (internal) and get translated to Japanese when you generate an email.

---

## Email Generation

1. Run a Shallow or Batch scan
2. Click **Generate Email** in the results panel
3. The AI writes a bilingual outreach email (Japanese Keigo + English) referencing specific things it found on the site
4. A Japanese-language **report card** is embedded — showing the score, issue counts, and 5 sample findings with explanations
5. Edit the recipient address, preview the email, and click **Send**

The email always:
- Opens with something genuine about the site (not a template opener)
- Mentions translation and localisation as the core service offered
- Frames everything as opportunity, never as criticism
- Includes a CTA button linking to your Shinrai Web portfolio

---

## Cost Reference (Anthropic)

| Operation | Model | Typical tokens | Approx. cost |
|-----------|-------|---------------|-------------|
| Shallow scan | Haiku | ~2,000 | ~$0.001 |
| Deep scan (10 pages) | Haiku | ~15,000 | ~$0.01 |
| Email generation | Sonnet | ~1,500 | ~$0.02 |
| JP translation (deep only) | Haiku | ~800 | ~$0.0004 |

Token costs are shown in the badge on each result. Ollama is free regardless of usage.

---

## Project Structure

```
prism/
├── src/                        # React frontend
│   ├── components/
│   │   ├── EmailDrawer.jsx     # Email generation + send UI
│   │   ├── SettingsModal.jsx   # All settings + Test Connection
│   │   ├── IssueCard.jsx       # Individual issue display
│   │   ├── ScoreRing.jsx       # Animated score ring
│   │   └── Sidebar.jsx         # Navigation
│   ├── pages/
│   │   ├── ScanPage.jsx        # URL input + scan controls
│   │   └── ResultsPage.jsx     # Results display + run history
│   └── stores/
│       ├── settingsStore.js    # Persisted settings (localStorage)
│       ├── scanStore.js        # Scan history (3 banks)
│       └── emailStore.js       # Email state + token tracking
├── backend/
│   └── main.py                 # FastAPI — scan, email, send endpoints
├── screenshot-service/
│   └── src/index.js            # Playwright screenshot + HTML capture
├── docker/                     # Dockerfiles for each service
├── docker-compose.yml
└── Makefile
```

---

## Troubleshooting

**Screenshot service can't reach the target site**
Some sites block headless browsers. Try a different URL or check `make logs` for Playwright errors.

**Ollama not reachable from Docker**
Make sure `ollama serve` is running on your host. The backend uses `host.docker.internal:11434` automatically. On Linux, confirm Docker has host networking enabled — the `extra_hosts` entry in `docker-compose.yml` handles this.

**AI returns malformed JSON**
The backend has automatic JSON repair built in. If it fails, check `make logs-backend` — the full raw response is printed. Try a more capable model.

**Gmail send fails**
Make sure you're using an **App Password**, not your regular Gmail password. Regular passwords are rejected by Gmail's SMTP endpoint.

**Changes not showing after restart**
Always use `make build` (or `docker compose up --build -d`) after code changes. `docker compose restart` only restarts the process — it does not rebuild the image.

---

## Part of Shinrai Web

Prism is an internal tool built to support [Shinrai Web](https://imrie83.github.io/shinrai/) — English localisation and web development for Japanese businesses.
