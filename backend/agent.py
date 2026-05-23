import os
import sys
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

# Resolve absolute path to the local mcp_server.py
current_dir = os.path.dirname(os.path.abspath(__file__))
mcp_server_path = os.path.join(current_dir, "mcp_server.py")

# Configure connection parameter to run mcp_server.py as a local stdio subprocess
server_params = StdioServerParameters(
    command=sys.executable,  # Use current Python environment interpreter
    args=[mcp_server_path],
    env=dict(os.environ)     # Forward environment variables (such as GITHUB_TOKEN, GEMINI_API_KEY)
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
