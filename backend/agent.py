import os
import sys
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

# Resolve absolute path to the local mcp_server.py
current_dir = os.path.dirname(os.path.abspath(__file__))
mcp_server_path = os.path.join(current_dir, "mcp_server.py")

# Forward environment variables safely (only strings, no NoneType to avoid Pydantic validation failure)
safe_env = {k: v for k, v in os.environ.items() if v is not None}
# Ensure both key names are forwarded — the ADK framework reads GOOGLE_API_KEY internally
_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if _api_key:
    safe_env["GOOGLE_API_KEY"] = _api_key
    safe_env["GEMINI_API_KEY"] = _api_key
if os.getenv("GITHUB_TOKEN"):
    safe_env["GITHUB_TOKEN"] = os.getenv("GITHUB_TOKEN")

server_params = StdioServerParameters(
    command=sys.executable,  # Use current Python environment interpreter
    args=[mcp_server_path],
    env=safe_env
)

# Connect to the local MCP server tools using McpToolset
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=server_params,
        timeout=30.0
    )
)

# Export the agent as github_card_agent
github_card_agent = Agent(
    name="github_card_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a GitHub profile analyst and dev card generator. "
        "When a user gives you a GitHub username, you ALWAYS follow this exact sequence: "
        "first call scrape_github, then analyze_profile with the result, "
        "then generate_card_html with all three inputs, then save_card. Never skip steps. "
        "Be enthusiastic about developers' work. If the profile is private or doesn't exist, say so clearly."
    ),
    tools=[mcp_toolset]
)
