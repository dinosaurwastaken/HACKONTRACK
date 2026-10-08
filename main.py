"""
TruthTrack — FastAPI Application
Serves the frontend, handles WebSocket fact-checking, and exposes analytics.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from services.verifier  import verify_claim, GOOGLE_API_KEY, _HAS_GENAI, SUPPORTED_LANGUAGES
from services.database  import init_db, save_check, get_stats, get_recent_checks

# ── App setup ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

app = FastAPI(
    title="TruthTrack",
    description="AI-powered multimodal fact-checking API",
    version="2.0.0",
)

static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    await init_db()


# ── Helper ────────────────────────────────────────────────────────────────────

def _current_mode() -> dict:
    ai_ready = bool(GOOGLE_API_KEY) and _HAS_GENAI
    return {
        "mode":            "ai" if ai_ready else "simulation",
        "label":           "🤖 AI Mode (Gemini)" if ai_ready else "🎭 Simulation Mode",
        "api_key_set":     bool(GOOGLE_API_KEY),
        "genai_installed": _HAS_GENAI,
    }


# ── HTTP routes ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "TruthTrack", **_current_mode()}


@app.get("/mode")
async def mode():
    return _current_mode()


@app.get("/api/languages")
async def api_languages():
    """Return the list of supported languages for the UI selector."""
    return [
        {"code": code, **meta}
        for code, meta in SUPPORTED_LANGUAGES.items()
    ]


@app.get("/api/stats")
async def api_stats():
    """Aggregate statistics for the analytics dashboard."""
    return await get_stats()


@app.get("/api/recent")
async def api_recent(limit: int = 20):
    """Most recent fact-checks (newest first)."""
    return await get_recent_checks(limit)


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/verify")
async def ws_verify(websocket: WebSocket):
    """
    Client → Server (JSON):
      { "claim_text": str, "file_data": b64|null, "file_mime": str|null, "file_name": str|null }

    Server → Client (multiple frames):
      { "type": "status",  "message": str, "step": int, "total_steps": int }
      { "type": "result",  ...verdict fields... }
      { "type": "error",   "message": str }
    """
    await websocket.accept()
    try:
        raw     = await websocket.receive_text()
        payload = json.loads(raw)

        claim_text: str       = payload.get("claim_text", "").strip()
        file_b64:   str|None  = payload.get("file_data")
        file_mime:  str|None  = payload.get("file_mime")
        file_name:  str|None  = payload.get("file_name")
        lang_code:  str       = payload.get("lang_code", "auto")

        file_bytes: bytes|None = None
        if file_b64:
            import base64
            file_bytes = base64.b64decode(file_b64)

        if not claim_text and not file_bytes:
            await websocket.send_json({"type": "error",
                                       "message": "Please provide text or attach a file."})
            return

        async def send_update(data: dict):
            await websocket.send_json(data)

        result = await verify_claim(
            claim_text=claim_text,
            file_bytes=file_bytes,
            file_mime=file_mime,
            send_update=send_update,
            lang_code=lang_code,
        )

        # ── Persist to database ──
        await save_check(
            claim_text   = claim_text or f"[File: {file_name}]",
            verdict      = result.get("verdict", "Unconfirmed"),
            confidence   = result.get("confidence", 0),
            summary      = result.get("summary", ""),
            key_findings = result.get("key_findings", []),
            sources      = result.get("sources", []),
            file_name    = file_name,
        )

        await websocket.send_json({"type": "result", **result})

    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "Invalid JSON payload."})
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": f"Server error: {exc}"})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── Dev entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
