import os
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Step 1: Load .env (local dev only; Cloud Run provides env vars directly) ──
load_dotenv()

# ── Step 2: Alias key names BEFORE any ADK import ────────────────────────────
# Google ADK internally calls genai.Client() which reads GOOGLE_API_KEY.
# Cloud Run is configured with GEMINI_API_KEY, so we set both here.
_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if _api_key:
    os.environ["GOOGLE_API_KEY"] = _api_key
    os.environ["GEMINI_API_KEY"] = _api_key
    logger.info("Gemini API key aliased to GOOGLE_API_KEY and GEMINI_API_KEY.")
else:
    # Log a warning but DO NOT raise — let the server start so Cloud Run health
    # checks pass. Requests will fail with a clear 503 if the key is missing.
    logger.warning("WARNING: No API key found (GEMINI_API_KEY / GOOGLE_API_KEY). "
                   "Requests to /generate will fail.")

# ── Step 3: Lazy ADK initialization ──────────────────────────────────────────
# We defer ALL ADK/Agent imports to first request so the container starts fast.
# Cloud Run requires the server to listen on PORT within the startup timeout.
# Heavy imports at module level have previously caused startup timeouts.
_runner = None
_types = None


def _get_runner():
    """Return the shared Runner, initializing it on the first call."""
    global _runner, _types

    if _runner is not None:
        return _runner, _types

    logger.info("Initializing Google ADK Runner (first request)…")

    # Late imports — these are slow and must not block server startup
    from google.genai import types as _t                          # noqa: PLC0415
    from google.adk.runners import Runner                         # noqa: PLC0415
    from google.adk.sessions import InMemorySessionService        # noqa: PLC0415
    from google.adk.memory import InMemoryMemoryService           # noqa: PLC0415
    from agent import github_card_agent                           # noqa: PLC0415

    _types = _t
    _runner = Runner(
        agent=github_card_agent,
        session_service=InMemorySessionService(),
        memory_service=InMemoryMemoryService(),
        app_name="github_card_generator",
        auto_create_session=True,
    )
    logger.info("Google ADK Runner initialized successfully.")
    return _runner, _types


# ── Step 4: FastAPI App ───────────────────────────────────────────────────────
app = FastAPI(
    title="GitHub Developer Card Generator API",
    description="FastAPI orchestration service backed by Google ADK & Gemini 2.5 Flash",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static cards directory — created at startup so it always exists
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
os.makedirs(os.path.join(static_dir, "cards"), exist_ok=True)


class GenerateRequest(BaseModel):
    username: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """GET /health — Standard health check for Google Cloud Run."""
    key_ok = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    return {
        "status": "ok",
        "service": "github-card-generator-backend",
        "api_key_loaded": key_ok,
    }


@app.post("/generate")
async def generate_card(request: GenerateRequest):
    """
    POST /generate — Runs the ADK Agent to fetch GitHub data, analyse the
    profile with Gemini, generate and save the HTML card, then returns it.
    """
    username = request.username.strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required.")

    # Ensure the API key is available before attempting anything
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        raise HTTPException(
            status_code=503,
            detail="Gemini API key not configured on the server. "
                   "Set GEMINI_API_KEY in Cloud Run environment variables.",
        )

    try:
        runner, types = _get_runner()
        prompt = f"Generate a dev card for {username}"

        async for event in runner.run_async(
            user_id=username,
            session_id=username,
            new_message=types.Content(parts=[types.Part.from_text(text=prompt)]),
        ):
            logger.info(f"[ADK Event — {username}]: {event}")

        # Read the saved card HTML
        file_path = os.path.join(static_dir, "cards", f"{username}.html")
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=500,
                detail="Agent finished but the card HTML file was not saved.",
            )

        with open(file_path, "r", encoding="utf-8") as f:
            card_html = f.read()

        return {
            "success": True,
            "username": username,
            "card_url": f"/card/{username}",
            "card_html": card_html,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating card for {username}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Card generation failed: {str(e)}")


@app.get("/card/{username}")
def get_card(username: str):
    """GET /card/{username} — Serves the saved developer card HTML file."""
    clean = "".join(c for c in username if c.isalnum() or c in "-_").lower()
    file_path = os.path.join(static_dir, "cards", f"{clean}.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Card for '{username}' not found.")
    return FileResponse(file_path)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
