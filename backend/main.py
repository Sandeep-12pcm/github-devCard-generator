import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load local environment variables
load_dotenv()

# Import the Google ADK and Gemini types dependencies
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from agent import github_card_agent

# Initialize FastAPI App
app = FastAPI(
    title="GitHub Developer Card Generator API",
    description="FastAPI orchestration service backed by Google ADK & Gemini 2.5 Flash"
)

# Add CORS middleware to allow calls from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Establish local storage directory for saved cards
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
os.makedirs(os.path.join(static_dir, "cards"), exist_ok=True)

# Set up in-memory session and memory services
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()

# Create the Runner bound to our agent and services
runner = Runner(
    agent=github_card_agent,
    session_service=session_service,
    memory_service=memory_service,
    app_name="github_card_generator",
    auto_create_session=True
)

class GenerateRequest(BaseModel):
    username: str


@app.post("/generate")
async def generate_card(request: GenerateRequest):
    """
    POST /generate - Creates or reuses a session, runs the ADK Agent sequence
    to scrape, analyze, generate, and save the developer card, streams progress,
    and returns the final preview card URL and card HTML content.
    """
    username = request.username.strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required.")
        
    try:
        # Prompt the ADK agent to perform the card generation sequence
        prompt = f"Generate a dev card for {username}"
        
        # Iterate over and stream/print the agent events to stdout as they occur
        async for event in runner.run_async(
            user_id=username,
            session_id=username,
            new_message=types.Content(parts=[types.Part.from_text(text=prompt)])
        ):
            print(f"[ADK Event - User: {username}]: {event}")

        # Resolve path to the generated HTML card file
        file_path = os.path.join(static_dir, "cards", f"{username}.html")
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=500, 
                detail="Agent finished execution but the card HTML file was not found."
            )

        # Read the compiled card HTML content
        with open(file_path, "r", encoding="utf-8") as f:
            card_html = f.read()

        return {
            "success": True,
            "username": username,
            "card_url": f"/card/{username}",
            "card_html": card_html
        }
    except Exception as e:
        print(f"Error generating card for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Card generation failed: {str(e)}")


@app.get("/card/{username}")
def get_card(username: str):
    """
    GET /card/{username} - Serves the saved developer card HTML file directly.
    """
    clean_username = "".join(c for c in username if c.isalnum() or c in "-_").lower()
    file_path = os.path.join(static_dir, "cards", f"{clean_username}.html")
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Developer card for '{username}' not found.")
        
    return FileResponse(file_path)


@app.get("/health")
def health():
    """
    GET /health - Standard health check route for Google Cloud Run.
    """
    return {"status": "ok", "service": "github-card-generator-backend"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
