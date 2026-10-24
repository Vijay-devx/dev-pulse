# DevPulse ⚡

> **High-Signal Tech Intelligence & News Aggregator for Software Engineers and Security Researchers.**

DevPulse cuts through marketing fluff, SEO listicles, and hype by providing a 3-stage progressive reading experience and algorithmic importance scoring.

---

## 🚀 Quickstart (Run Locally in 60 Seconds)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
The app runs locally out of the box with realistic seed data and heuristic fallbacks if no LLM key is provided.

To enable LLM processing with OpenAI, Anthropic, or Gemini, copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
And set your API key:
```ini
LLM_PROVIDER=openai           # or anthropic | gemini | openai_compatible
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

### 3. Launch DevPulse
```bash
python main.py
```
Open your browser at **[http://localhost:8000](http://localhost:8000)**.

---

## 🧪 Verification & Testing
Run the automated test suite verifying all routes, HTMX partials, drawer state, and full reader:
```bash
python test_app.py
```

---

## 🏛️ Architecture & Information Flow

### The 3-Stage Progressive Reading Workflow
1. **Stage 1: Main Feed Card**
   - De-clickbaited technical headlines
   - Category pills (`[Reverse Engineering]`, `[Bugs & CVEs]`, etc.)
   - Importance badges (e.g., `🚨 Critical RCE`, `🔥 HN 487 pts`, `⚡ Depth: 9/10`)
   - Read time estimates (`1m Crux • 6m Full Read`)
   - Clicking any card opens **Stage 2** instantly via HTMX without page reload.

2. **Stage 2: The Crux Drawer (Slide-Over)**
   - 📌 **What It Is About**: 2–3 sentence executive technical summary.
   - 📈 **Why It Is Trending**: The exact catalyst (PoC release, benchmark, severity).
   - ⚙️ **Key Technical Details**: 3–4 under-the-hood implementation bullets.
   - 🎯 **Impact**: Direct developer action + ecosystem impact.
   - Bookmark toggle and external source links.
   - Primary CTA: **`[ Read Full Article (Clean Reader) → ]`** transitioning to **Stage 3**.

3. **Stage 3: Full Clean Reader**
   - Distraction-free typography with code syntax highlighting.
   - "Back to Crux" instant navigation.
   - Graceful fallback with direct external links if full-text extraction was restricted.

---

## 📑 Categorized Sections
- **⚡ Daily Briefing (Default Tab):** High-signal stories with `importance_score >= 80`.
- **🔬 Reverse Engineering & Low-Level (`rea`):** Binary exploitation, firmware, malware analysis.
- **🚨 Bugs, CVEs & Post-Mortems (`bugs_cves`):** Zero-days, language engine bugs, cloud outages.
- **🤖 Applied AI & Dev Workflows (`applied_ai`):** Coding agents, local LLMs, real dev utility.
- **🛠️ Dev Quality-of-Life (`dev_qol`):** CLI tools, dotfile utilities, IDE extensions.
- **🏗️ High-Impact Tech & Architecture (`architecture`):** Database scaling, compiler breakthroughs, distributed systems.

---

## 🔄 Live Ingestion & LLM Pipeline
- **Sources:** Hacker News Top/Best API, curated RSS feeds (Project Zero, r/ReverseEngineering, Lobste.rs, GitHub Blog, Meta Engineering, PHP/Rust/Python releases).
- **Background Scheduler:** Powered by `APScheduler` (syncs every 60 minutes) + manual "Sync Now" button in the UI.
- **Full Text Extractor:** `trafilatura` for clean web content extraction.
- **LLM Processor:** Formulates structured JSON analysis with schema enforcement and keyword-based fallback classifier.
