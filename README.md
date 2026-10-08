# TruthTrack 🛡️ — AI Fact-Checking Web App

> "Is This Forward True?" — powered by Google Gemini & FastAPI

## Quick Start

```bash
# 1. Clone / enter the project directory
cd HACKONTRACK

# 2. Activate the virtual environment
.\venv\Scripts\Activate.ps1       # Windows PowerShell
# source venv/bin/activate         # macOS / Linux

# 3. (Optional) Set your Gemini API key for real AI analysis
copy .env.example .env
# Edit .env and paste your GOOGLE_API_KEY

# 4. Start the server
.\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000

# 5. Open http://localhost:8000
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI 0.115 |
| Real-time | WebSockets (native FastAPI) |
| AI Core | Google Gemini 2.0 Flash |
| Frontend | HTML + Vanilla JS + Tailwind CSS (CDN) |
| File handling | python-multipart, PyPDF2, Pillow |
| Server | Uvicorn (ASGI) |

## Supported Input Formats

| Type | Formats |
|------|---------|
| Text | Free-form paste / typed claim |
| Image | PNG, JPG, WEBP (multimodal Gemini) |
| Document | PDF (text extraction via PyPDF2) |
| Audio | MP3, WAV (Gemini audio understanding) |

## Verdict Types

| Verdict | Meaning |
|---------|---------|
| ✅ Verified | Claim is factually accurate |
| ❌ False | Claim is factually incorrect |
| 🕰️ Outdated | Was true, no longer accurate |
| ⚖️ Partly Supported | Partially correct |
| ❓ Unconfirmed | Insufficient evidence |

## Project Structure

```
HACKONTRACK/
├── main.py                  # FastAPI app + WebSocket /ws/verify
├── services/
│   ├── __init__.py
│   └── verifier.py          # Multimodal AI pipeline + simulation fallback
├── templates/
│   └── index.html           # Single-page frontend (Tailwind + Vanilla JS)
├── static/                  # Static assets (CSS/JS if needed)
├── uploads/                 # Temp upload directory
├── requirements.txt
├── .env.example             # Copy to .env and add GOOGLE_API_KEY
└── README.md
```

## WebSocket Protocol

**Client → Server** (single JSON frame):
```json
{
  "claim_text": "The forwarded message text…",
  "file_data":  "<base64-encoded bytes | null>",
  "file_mime":  "image/jpeg | application/pdf | audio/mpeg | null",
  "file_name":  "screenshot.jpg | null"
}
```

**Server → Client** (multiple frames):
```json
{ "type": "status", "message": "🔍 Extracting text…" }
{ "type": "result", "verdict": "False", "confidence": 91,
  "summary": "…", "key_findings": […], "sources": […] }
{ "type": "error",  "message": "…" }
```

## Simulation Mode

When `GOOGLE_API_KEY` is not set, the app runs in **simulation mode** — it streams realistic status steps with `asyncio.sleep` delays and returns one of three pre-defined verdicts deterministically (based on input length). This lets you demo the full UI flow without an API key.
