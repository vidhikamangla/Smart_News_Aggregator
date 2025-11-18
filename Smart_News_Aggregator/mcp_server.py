# mcp_server.py
"""
MCP Server exposing Smart News Aggregator ADK tools
This allows external MCP clients (including Claude Desktop, other ADK agents, or CrewAI agents) 
to access your news scraping tools.
"""

import asyncio
import json
import os
from dotenv import load_dotenv
from typing import List, Dict, Any

# MCP Server Imports
from mcp import types as mcp_types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio

# ADK Tool Imports
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type

# Import your scraper functions
from .Scrapers.entertainment_scraper import scrape_entertainment_top_n
from .Scrapers.sports_scraper import scrape_sports_top_n
from .Scrapers.international_scraper import scrape_international_top_n
from .Scrapers.national_scraper import scrape_national_top_n
from .Scrapers.states_scraper import scrape_states_top_n

# Load environment variables
load_dotenv()

# --- Prepare ADK Tools ---
print("Initializing ADK news scraper tools for MCP exposure...")

# Wrapper functions that return structured data
def get_states_news_mcp(state: str, limit: int = 10) -> Dict[str, Any]:
    """Fetch state/city-specific news articles."""
    try:
        articles = scrape_states_top_n(state, limit)
        return {
            "status": "success",
            "category": f"states_{state}",
            "count": len(articles),
            "articles": articles
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def get_national_news_mcp(limit: int = 10) -> Dict[str, Any]:
    """Fetch national news articles."""
    try:
        articles = scrape_national_top_n(limit)
        return {
            "status": "success",
            "category": "national",
            "count": len(articles),
            "articles": articles
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def get_international_news_mcp(limit: int = 10) -> Dict[str, Any]:
    """Fetch international news articles."""
    try:
        articles = scrape_international_top_n(limit)
        return {
            "status": "success",
            "category": "international",
            "count": len(articles),
            "articles": articles
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def get_sports_news_mcp(limit: int = 10) -> Dict[str, Any]:
    """Fetch sports news articles."""
    try:
        articles = scrape_sports_top_n(limit)
        return {
            "status": "success",
            "category": "sports",
            "count": len(articles),
            "articles": articles
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def get_entertainment_news_mcp(limit: int = 10) -> Dict[str, Any]:
    """Fetch entertainment news articles."""
    try:
        articles = scrape_entertainment_top_n(limit)
        return {
            "status": "success",
            "category": "entertainment",
            "count": len(articles),
            "articles": articles
        }
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

# Create FunctionTools from your scraper functions
adk_tools_to_expose = [
    FunctionTool(get_states_news_mcp),
    FunctionTool(get_national_news_mcp),
    FunctionTool(get_international_news_mcp),
    FunctionTool(get_sports_news_mcp),
    FunctionTool(get_entertainment_news_mcp),
]

print(f"Initialized {len(adk_tools_to_expose)} ADK tools for MCP exposure")
for tool in adk_tools_to_expose:
    print(f"  - {tool.name}")

# --- MCP Server Setup ---
print("Creating MCP Server instance...")
app = Server("smart-news-aggregator-mcp-server")

@app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    """MCP handler to list available news scraper tools."""
    print("MCP Server: Received list_tools request.")
    mcp_tool_schemas = []
    
    for adk_tool in adk_tools_to_expose:
        mcp_tool_schema = adk_to_mcp_tool_type(adk_tool)
        mcp_tool_schemas.append(mcp_tool_schema)
        print(f"MCP Server: Advertising tool: {mcp_tool_schema.name}")
    
    return mcp_tool_schemas

@app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.Content]:
    """MCP handler to execute a news scraper tool call."""
    print(f"MCP Server: Received call_tool request for '{name}' with args: {arguments}")
    
    # Find the matching ADK tool
    matching_tool = None
    for tool in adk_tools_to_expose:
        if tool.name == name:
            matching_tool = tool
            break
    
    if matching_tool:
        try:
            # Execute the ADK tool
            result = await matching_tool.run_async(
                args=arguments,
                tool_context=None,
            )
            print(f"MCP Server: Tool '{name}' executed successfully")
            
            # Format response as JSON
            response_text = json.dumps(result, indent=2)
            return [mcp_types.TextContent(type="text", text=response_text)]
            
        except Exception as e:
            print(f"MCP Server: Error executing tool '{name}': {e}")
            error_text = json.dumps({
                "status": "error",
                "error_message": f"Failed to execute tool '{name}': {str(e)}"
            })
            return [mcp_types.TextContent(type="text", text=error_text)]
    else:
        print(f"MCP Server: Tool '{name}' not found")
        error_text = json.dumps({
            "status": "error",
            "error_message": f"Tool '{name}' not implemented by this server."
        })
        return [mcp_types.TextContent(type="text", text=error_text)]

# --- MCP Server Runner ---
async def run_mcp_stdio_server():
    """Runs the MCP server over standard input/output."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        print("MCP Stdio Server: Starting handshake with client...")
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=app.name,
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
        print("MCP Stdio Server: Connection closed.")

if __name__ == "__main__":
    print("=" * 60)
    print("Smart News Aggregator MCP Server")
    print("Exposing news scraper tools via MCP protocol")
    print("=" * 60)
    try:
        asyncio.run(run_mcp_stdio_server())
    except KeyboardInterrupt:
        print("\nMCP Server stopped by user.")
    except Exception as e:
        print(f"MCP Server error: {e}")
        raise
    finally:
        print("MCP Server process exiting.")