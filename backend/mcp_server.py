import os
import httpx
import json
from typing import Dict, Any, List, Literal
from fastmcp import FastMCP
from google import genai
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

# Initialize FastMCP Server
mcp = FastMCP("GitHubCardGenerator")

# Base GitHub configuration
GITHUB_API_URL = "https://api.github.com"
token = os.getenv("GITHUB_TOKEN")
headers = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "GitHub-Dev-Card-Generator"
}
if token:
    headers["Authorization"] = f"token {token}"

# Define the Pydantic schema for structured output from Gemini
class ProfileAnalysis(BaseModel):
    developer_vibe: str
    top_skills: List[str]
    fun_fact: str
    card_theme: Literal["hacker", "builder", "researcher", "designer", "open-source-hero"]


@mcp.tool
async def scrape_github(username: str) -> dict:
    """
    Scrapes a user's GitHub profile, their top 6 repositories by stars,
    and aggregates their most used languages.
    
    Args:
        username (str): The GitHub username to scrape.
        
    Returns:
        dict: Scraped metrics including bio, followers, repos, and language analysis.
    """
    async with httpx.AsyncClient() as client:
        # Fetch public profile details
        user_url = f"{GITHUB_API_URL}/users/{username}"
        user_response = await client.get(user_url, headers=headers)
        
        if user_response.status_code == 404:
            raise ValueError(f"GitHub user '{username}' not found.")
        user_response.raise_for_status()
        profile = user_response.json()
        
        # Fetch all public repositories (up to 100)
        repos_url = f"{GITHUB_API_URL}/users/{username}/repos?per_page=100&sort=updated"
        repos_response = await client.get(repos_url, headers=headers)
        repos_response.raise_for_status()
        repos = repos_response.json()

    # Aggregate languages across all public repositories
    languages = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            languages[lang] = languages.get(lang, 0) + 1
            
    # Sort languages by count descending
    sorted_languages = dict(sorted(languages.items(), key=lambda item: item[1], reverse=True))

    # Identify top 6 repositories by stars (favoring original repos over forks)
    original_repos = [r for r in repos if not r.get("fork")]
    fork_repos = [r for r in repos if r.get("fork")]
    
    sorted_originals = sorted(original_repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)
    sorted_forks = sorted(fork_repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)
    
    combined_repos = sorted_originals + sorted_forks
    top_6 = combined_repos[:6]
    
    processed_repos = []
    for r in top_6:
        processed_repos.append({
            "name": r.get("name"),
            "stars": r.get("stargazers_count", 0),
            "language": r.get("language") or "Plain Text",
            "description": r.get("description") or "No description provided."
        })

    return {
        "name": profile.get("name") or username,
        "bio": profile.get("bio") or "No bio provided.",
        "location": profile.get("location") or "Cloud Space",
        "public_repos": profile.get("public_repos", 0),
        "followers": profile.get("followers", 0),
        "avatar_url": profile.get("avatar_url") or "",
        "top_repos": processed_repos,
        "languages": sorted_languages
    }


@mcp.tool
async def analyze_profile(github_data: dict) -> dict:
    """
    Uses Gemini 2.5 Flash to analyze GitHub statistics and formulate a developer persona,
    top skills, fun facts, and an ideal visual theme.
    
    Args:
        github_data (dict): The dictionary returned by scrape_github.
        
    Returns:
        dict: Profile analysis JSON containing vibe, skills, fun fact, and card theme.
    """
    client = genai.Client()
    
    prompt = f"""
    Analyze the following GitHub developer profile data:
    Name: {github_data.get('name')}
    Bio: {github_data.get('bio')}
    Location: {github_data.get('location')}
    Public Repos Count: {github_data.get('public_repos')}
    Followers: {github_data.get('followers')}
    Top Repositories: {json.dumps(github_data.get('top_repos'))}
    Language Mix: {json.dumps(github_data.get('languages'))}
    
    Generate:
    1. developer_vibe: A witty, extremely descriptive 1-sentence summary summarizing their persona and stack (e.g. "An elegant full-stack architect who ships robust FastAPI backends while crafting sleek CSS in their sleep.").
    2. top_skills: A list of exactly 3 prominent technical or architectural skills inferred from their repos and languages (e.g. ["Asynchronous Event Loops", "Stateless Architecture Design", "Responsive Layout Composition"]).
    3. fun_fact: A highly clever, custom fun fact inferred from their codebase or statistics.
    4. card_theme: Pick exactly one visual layout theme that represents their profile:
       - "hacker": low-level languages (C, C++, Rust, Go), command-line tools, terminal utilities.
       - "builder": full-stack/backends (Python, Java, C#), complex databases, architecture.
       - "researcher": data science, AI/ML, academic research, algorithms, Jupyter notebooks.
       - "designer": front-end heavy (HTML, CSS, TypeScript), design assets, visual UX layout.
       - "open-source-hero": massive followers count, huge repository count, significant stargazers counts.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config={
            'response_mime_type': 'application/json',
            'response_schema': ProfileAnalysis,
        }
    )
    
    if hasattr(response, "parsed"):
        analysis: ProfileAnalysis = response.parsed
        return analysis.model_dump()
    
    # Fallback to standard parsing
    return json.loads(response.text)


@mcp.tool
async def generate_card_html(username: str, github_data: dict, analysis: dict) -> str:
    """
    Generates a beautiful self-contained HTML page representing the developer card
    styled according to the chosen theme.
    
    Args:
        username (str): The GitHub handle.
        github_data (dict): Profile statistics.
        analysis (dict): The generated Gemini personality analysis.
        
    Returns:
        str: Fully compiled visual HTML card.
    """
    theme = analysis.get("card_theme", "builder")
    name = github_data.get("name", username)
    avatar = github_data.get("avatar_url", "")
    vibe = analysis.get("developer_vibe", "")
    skills = analysis.get("top_skills", [])
    repos_count = github_data.get("public_repos", 0)
    followers = github_data.get("followers", 0)
    repos = github_data.get("top_repos", [])[:3] # Extract top 3 repos for the card display
    fun_fact = analysis.get("fun_fact", "")
    location = github_data.get("location", "Cloud")

    # Dynamic Theme Configuration Details
    theme_styles = {
        "hacker": {
            "bg": "#030303",
            "card_bg": "rgba(10, 10, 10, 0.95)",
            "border": "1px solid rgba(0, 255, 0, 0.25)",
            "text": "#00ff00",
            "text_secondary": "#00aa00",
            "accent": "#00ff00",
            "accent_gradient": "linear-gradient(135deg, #00ff00 0%, #003300 100%)",
            "font": "'Fira Code', monospace",
            "shadow": "0 0 30px rgba(0, 255, 0, 0.15)",
            "badge_bg": "rgba(0, 255, 0, 0.08)",
            "badge_border": "1px solid #00ff00",
            "corners": "12px"
        },
        "builder": {
            "bg": "#0f172a",
            "card_bg": "rgba(30, 41, 59, 0.75)",
            "border": "1px solid rgba(255, 255, 255, 0.08)",
            "text": "#f8fafc",
            "text_secondary": "#94a3b8",
            "accent": "#3b82f6",
            "accent_gradient": "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
            "font": "'Inter', sans-serif",
            "shadow": "0 15px 35px rgba(0, 0, 0, 0.5)",
            "badge_bg": "rgba(59, 130, 246, 0.1)",
            "badge_border": "1px solid rgba(59, 130, 246, 0.4)",
            "corners": "18px"
        },
        "researcher": {
            "bg": "#080710",
            "card_bg": "rgba(23, 23, 37, 0.8)",
            "border": "1px solid rgba(217, 119, 6, 0.25)",
            "text": "#f3f4f6",
            "text_secondary": "#9ca3af",
            "accent": "#fbbf24",
            "accent_gradient": "linear-gradient(135deg, #fbbf24 0%, #b45309 100%)",
            "font": "'Playfair Display', 'Georgia', serif",
            "shadow": "0 20px 40px rgba(0, 0, 0, 0.6)",
            "badge_bg": "rgba(251, 191, 36, 0.1)",
            "badge_border": "1px solid rgba(251, 191, 36, 0.4)",
            "corners": "16px"
        },
        "designer": {
            "bg": "#0f051d",
            "card_bg": "rgba(25, 12, 45, 0.75)",
            "border": "1px solid rgba(236, 72, 153, 0.25)",
            "text": "#fdf2f8",
            "text_secondary": "#f472b6",
            "accent": "#ec4899",
            "accent_gradient": "linear-gradient(135deg, #ec4899 0%, #f43f5e 50%, #f59e0b 100%)",
            "font": "'Plus Jakarta Sans', sans-serif",
            "shadow": "0 20px 45px rgba(236, 72, 153, 0.2)",
            "badge_bg": "rgba(236, 72, 153, 0.08)",
            "badge_border": "1px solid rgba(236, 72, 153, 0.4)",
            "corners": "28px"
        },
        "open-source-hero": {
            "bg": "#022c22",
            "card_bg": "rgba(6, 78, 59, 0.85)",
            "border": "1px solid rgba(16, 185, 129, 0.3)",
            "text": "#f0fdf4",
            "text_secondary": "#a7f3d0",
            "accent": "#10b981",
            "accent_gradient": "linear-gradient(135deg, #10b981 0%, #047857 100%)",
            "font": "'Plus Jakarta Sans', sans-serif",
            "shadow": "0 15px 40px rgba(2, 44, 34, 0.6)",
            "badge_bg": "rgba(16, 185, 129, 0.12)",
            "badge_border": "1px solid rgba(16, 185, 129, 0.5)",
            "corners": "22px"
        }
    }

    # Extract styled options
    style = theme_styles.get(theme, theme_styles["builder"])
    
    # Formulate top repos cards UI
    repos_html = ""
    for r in repos:
        repos_html += f"""
        <div class="repo-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
                <span class="repo-name">{r.get('name')}</span>
                <span class="repo-stars">⭐ {r.get('stars')}</span>
            </div>
            <div class="repo-desc">{r.get('description')}</div>
            <div style="font-size: 0.7rem; color: {style['accent']}; font-weight: bold; margin-top: 0.4rem;">
                ● {r.get('language')}
            </div>
        </div>
        """

    # Formulate skills HTML
    skills_html = ""
    for sk in skills:
        skills_html += f'<span class="skill-badge">{sk}</span>'

    # Build entire self-contained card HTML template
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name}'s Portfolio Badge</title>
    <!-- Imports of beautiful, premium fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;600&family=Inter:wght@300;400;600;800&family=Playfair+Display:ital,wght@0,600;1,400&family=Plus+Jakarta+Sans:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            background-color: {style['bg']};
            color: {style['text']};
            font-family: {style['font']};
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 1.5rem;
            overflow: hidden;
        }}
        .card {{
            width: 100%;
            max-width: 440px;
            background: {style['card_bg']};
            border: {style['border']};
            border-radius: {style['corners']};
            padding: 2.2rem 1.8rem;
            box-shadow: {style['shadow']};
            backdrop-filter: blur(12px);
            position: relative;
            transition: transform 0.3s ease;
        }}
        .card:hover {{
            transform: scale(1.015);
        }}
        /* Card header section */
        .profile-header {{
            display: flex;
            align-items: center;
            gap: 1.25rem;
            margin-bottom: 1.25rem;
        }}
        .avatar {{
            width: 72px;
            height: 72px;
            border-radius: 50%;
            border: 2px solid {style['accent']};
            object-fit: cover;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }}
        .name {{
            font-size: 1.45rem;
            font-weight: 800;
            line-height: 1.2;
            letter-spacing: -0.5px;
        }}
        .location {{
            font-size: 0.8rem;
            color: {style['text_secondary']};
            margin-top: 0.25rem;
        }}
        /* Vibe bio box */
        .vibe-box {{
            font-style: italic;
            font-size: 0.85rem;
            line-height: 1.5;
            color: {style['text_secondary']};
            border-left: 2px solid {style['accent']};
            padding-left: 0.75rem;
            margin-bottom: 1.5rem;
        }}
        /* Specializations */
        .skills-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
        }}
        .skill-badge {{
            font-size: 0.7rem;
            padding: 0.35rem 0.75rem;
            border-radius: 999px;
            background: {style['badge_bg']};
            border: {style['badge_border']};
            color: {style['text']};
            font-weight: 600;
        }}
        /* Profile stats layout */
        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            background: rgba(255, 255, 255, 0.02);
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding: 0.85rem 0;
            margin-bottom: 1.5rem;
            text-align: center;
        }}
        .stat-value {{
            font-size: 1.25rem;
            font-weight: 800;
            color: {style['text']};
        }}
        .stat-label {{
            font-size: 0.75rem;
            color: {style['text_secondary']};
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 0.15rem;
        }}
        /* Top showcase repos */
        .repos-section-title {{
            font-size: 0.75rem;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: {style['text_secondary']};
            margin-bottom: 0.75rem;
        }}
        .repo-card {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 0.75rem;
            margin-bottom: 0.6rem;
            transition: all 0.2s ease;
        }}
        .repo-card:hover {{
            background: rgba(255, 255, 255, 0.06);
            border-color: rgba(255, 255, 255, 0.1);
        }}
        .repo-name {{
            font-weight: 700;
            font-size: 0.85rem;
        }}
        .repo-stars {{
            font-size: 0.75rem;
            color: {style['text_secondary']};
        }}
        .repo-desc {{
            font-size: 0.75rem;
            line-height: 1.4;
            color: {style['text_secondary']};
            margin-top: 0.25rem;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        /* Fun facts footer badge */
        .fun-fact-container {{
            margin-top: 1.25rem;
            font-size: 0.7rem;
            text-align: center;
            color: {style['text_secondary']};
            background: rgba(255, 255, 255, 0.02);
            padding: 0.5rem;
            border-radius: 8px;
            border: 1px dashed rgba(255,255,255,0.06);
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="profile-header">
            <img class="avatar" src="{avatar}" alt="{name}">
            <div>
                <div class="name">{name}</div>
                <div class="location">📍 {location}</div>
            </div>
        </div>
        
        <div class="vibe-box">
            "{vibe}"
        </div>
        
        <div class="skills-container">
            {skills_html}
        </div>
        
        <div class="stats-grid">
            <div>
                <div class="stat-value">{repos_count}</div>
                <div class="stat-label">Repositories</div>
            </div>
            <div>
                <div class="stat-value">{followers}</div>
                <div class="stat-label">Followers</div>
            </div>
        </div>
        
        <div class="repos-section-title">Top Showcase Repos</div>
        <div style="max-height: 240px; overflow-y: auto; padding-right: 0.25rem;">
            {repos_html}
        </div>
        
        <div class="fun-fact-container">
            💡 <strong>Fun Fact:</strong> {fun_fact}
        </div>
    </div>
</body>
</html>"""
    return html_template


@mcp.tool
async def save_card(username: str, html: str) -> str:
    """
    Saves the generated HTML developer card locally to static/cards/{username}.html
    and returns the relative URL path.
    
    Args:
        username (str): The GitHub handle to name the file.
        html (str): The self-contained HTML content of the card.
        
    Returns:
        str: Relative URL route to view the saved card.
    """
    clean_username = "".join(c for c in username if c.isalnum() or c in "-_").lower()
    
    # Set up folders relative to the current server location
    current_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(current_dir, "static", "cards")
    os.makedirs(static_dir, exist_ok=True)
    
    file_path = os.path.join(static_dir, f"{clean_username}.html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    return f"/static/cards/{clean_username}.html"


if __name__ == "__main__":
    mcp.run()
