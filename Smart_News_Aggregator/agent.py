# agent.py
"""
Enhanced Smart News Aggregator Agent with:
1. MCP integration (expose tools to external clients)
2. A2A integration (communicate with CrewAI agent)
3. Original ADK functionality
"""

import datetime
import json
import logging
import asyncio
import uuid
import time
import os
from typing import Optional, Dict, Any, Set, List
from pydantic import BaseModel
from google.genai import types
from google.genai import types as genai_types

from google.adk.agents import LlmAgent, SequentialAgent, ParallelAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.function_tool import FunctionTool
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.adk.events import Event, EventActions

# MCP integration
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from email.mime.text import MIMEText
import smtplib

from .Scrapers.entertainment_scraper import scrape_entertainment_top_n
from .Scrapers.sports_scraper import scrape_sports_top_n
from .Scrapers.international_scraper import scrape_international_top_n
from .Scrapers.national_scraper import scrape_national_top_n
from .Scrapers.states_scraper import scrape_states_top_n

# A2A CrewAI integration
from .crewai_bridge_agent import (
    analyze_news_with_crewai,
    get_trend_analysis,
    fact_check_articles
)

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
STYLE_OF_WRITING = os.getenv("STYLE_OF_WRITING", "sarcastic")
TARGET_LANGUAGE = os.getenv("TARGET_LANGUAGE", "esp")
MCP_SERVER_PATH = os.path.join(os.path.dirname(__file__), "mcp_server.py")

# Constants from original agent
class NewsItem(BaseModel):
    title: str
    link: str
    date: str
    author: Optional[str] = ""
    article: Optional[str] = ""
    image_url: Optional[str] = None

BANNED_WORDS: Set[str] = {
    "kill yourself", "how to make a bomb", "i will kill you", "rape",
    "nazi", "faggot", "retard", "child assault", "autistic", "murder"
}

NEWS_KEYWORDS: Set[str] = {
    "news", "headlines", "article", "happening in", "sports",
    "entertainment", "politics", "business", "tech", "latest",
    "updates", "breaking", "tell me about", "what's new", "information",
    "analyze", "trends", "fact check", "insights"
}

VALID_STATES: Set[str] = {
    "mumbai", "delhi", "bengaluru", "kolkata", "chennai", "pune",
    "hyderabad", "ahmedabad", "maharashtra", "karnataka",
    "west bengal", "tamil nadu", "gujarat", "uttar pradesh",
    "rajasthan", "punjab", "kerala", "andhra pradesh", "goa"
}

# --- Email Tool (from original) ---
def send_email_smtp(to_addr: str, subject: str, html_body: str) -> str:
    SMTP_SERVER = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASS = os.environ.get("SMTP_PASS")
    FROM_ADDR = os.environ.get("FROM_ADDR", "no-reply@example.com")

    if not SMTP_USER or not SMTP_PASS:
        return "ERROR: missing SMTP_USER/SMTP_PASS"
    if not to_addr or "@" not in to_addr:
        return "ERROR: invalid recipient email"
    if not subject or not html_body:
        return "ERROR: subject/body required"

    try:
        msg = MIMEText(html_body, "html", "utf-8")
        msg["Subject"] = subject[:90]
        msg["From"] = FROM_ADDR
        msg["To"] = to_addr

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return "OK"
    except Exception as e:
        return f"ERROR: {e}"

# --- Callbacks (from original) ---
def before_agent_callback(callback_context: CallbackContext):
    state = callback_context.state
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["run_counter"] = state.get("run_counter", 0) + 1
    state["last_agent_start"] = timestamp
    print(f"\n=== AGENT START ===")
    print(f"Run #: {state['run_counter']}")
    print(f"Timestamp: {timestamp}")
    return None

def after_agent_callback(callback_context: CallbackContext):
    state = callback_context.state
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== AGENT END ===")
    state["last_agent_end"] = timestamp
    return None

# --- Guardrails (from original) ---
def input_guardrail(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    last_user_text = ""
    if llm_request.contents:
        for c in reversed(llm_request.contents):
            if c.role == "user" and c.parts and c.parts[0].text:
                last_user_text = c.parts[0].text.lower()
                break

    if not last_user_text:
        return None

    if any(w in last_user_text for w in BANNED_WORDS):
        msg = "!!! I cannot process this request due to a content policy violation."
        callback_context.state["abort_pipeline"] = True
        callback_context.state["guardrail_output"] = msg
        return LlmResponse(content=genai_types.Content(role="model", parts=[genai_types.Part(text=msg)]))

    if not any(w in last_user_text for w in NEWS_KEYWORDS):
        msg = "📰 I am a news assistant. I can fetch news, headlines, articles, and provide analysis."
        callback_context.state["abort_pipeline"] = True
        callback_context.state["guardrail_output"] = msg
        return LlmResponse(content=genai_types.Content(role="model", parts=[genai_types.Part(text=msg)]))

    return None

def tool_guardrail(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext) -> Optional[Dict]:
    if tool.name == "get_states_news":
        state = args.get("state", "").lower().strip()
        if not state:
            return {"status": "error", "error_message": "You asked for state news but did not provide a state or city."}
        if state not in VALID_STATES:
            return {"status": "error", "error_message": f"Policy Error: '{state}' is not a valid state or city."}
    return None

# --- Scraper Functions (from original) ---
def wrap(items: list) -> List[NewsItem]:
    return [NewsItem(**item) for item in items if item.get("article")]

def get_states_news(state: str, limit: int = 10) -> List[NewsItem]:
    return wrap(scrape_states_top_n(state, limit))

def get_national_news(limit: int = 10) -> List[NewsItem]:
    return wrap(scrape_national_top_n(limit))

def get_international_news(limit: int = 10) -> List[NewsItem]:
    return wrap(scrape_international_top_n(limit))

def get_sports_news(limit: int = 10) -> List[NewsItem]:
    return wrap(scrape_sports_top_n(limit))

def get_entertainment_news(limit: int = 10) -> List[NewsItem]:
    return wrap(scrape_entertainment_top_n(limit))

# --- A2A Integration: CrewAI Analysis Tools ---
def analyze_news_crewai(analysis_type: str = "comprehensive") -> Dict[str, Any]:
    """
    A2A Tool: Analyze scraped news using CrewAI agent
    This reads from state['scraper_output'] and performs advanced analysis
    """
    return {
        "tool": "analyze_news_crewai",
        "analysis_type": analysis_type,
        "note": "This will be processed by the crewai_analyzer_agent"
    }

# --- Agent Definitions ---

# 1. Scraper Agent (unchanged from original)
scraper_agent = LlmAgent(
    model="gemini-2.5-flash-lite",
    name="scraper_agent",
    instruction="Always call a tool to fetch real scraped news. Never fabricate news.",
    description="Fetches real scraped news and stores structured data.",
    tools=[
        get_states_news,
        get_national_news,
        get_international_news,
        get_sports_news,
        get_entertainment_news,
    ],
    output_key="scraper_output",
    before_model_callback=input_guardrail,
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
    before_tool_callback=tool_guardrail,
)

# 2. NEW: CrewAI Analyzer Agent (A2A Integration)
crewai_analyzer_agent = LlmAgent(
    model="gemini-2.5-flash-lite",
    name="crewai_analyzer_agent",
    description="Uses CrewAI to perform deep analysis on scraped news articles",
    instruction="""
    You have access to advanced AI analysis via CrewAI agents.
    
    If the user asks for:
    - "analyze" or "insights" → call analyze_news_with_crewai with type="comprehensive"
    - "trends" or "what's trending" → call get_trend_analysis
    - "fact check" or "verify" → call fact_check_articles
    
    Input comes from state['scraper_output']. Convert NewsItem objects to dicts before calling.
    Store the analysis result in your output.
    """,
    tools=[
        FunctionTool(analyze_news_with_crewai),
        FunctionTool(get_trend_analysis),
        FunctionTool(fact_check_articles),
    ],
    output_key="crewai_analysis",
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)

# 3. Summarizer Agent (updated to handle both news and analysis)
summariser_agent = LlmAgent(
    model="gemini-2.5-flash-lite",
    name="summariser_agent",
    description=f"Summarizes scraped articles and analysis in a {STYLE_OF_WRITING} tone.",
    instruction=(
        f"You will receive:\n"
        "1. scraper_output (list of news items)\n"
        "2. crewai_analysis (optional AI analysis)\n"
        "3. OR a guardrail message\n\n"
        "If input is a guardrail message, repeat it as-is.\n\n"
        f"Otherwise, write a *clean markdown news report* in a *{STYLE_OF_WRITING} tone*.\n\n"
        "CRITICAL RULES:\n"
        "• Output ONLY markdown.\n"
        "• For each article:\n"
        "   ## Title\n"
        "   *Date:* | *Author:* | [Source](link) | *Image:* image_url\n"
        "   Summary paragraph (120-160 words).\n"
        "• If crewai_analysis exists, add a section:\n"
        "   ## AI Analysis\n"
        "   [CrewAI insights here]\n"
        "• No bullet lists or prefaces.\n"
    ),
    output_key="summary_output",
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)

# 4. Multilingual Agent (unchanged)
multilingual_agent = LlmAgent(
    name="MultilingualTranslatorAgent",
    model="gemini-2.5-flash-lite",
    instruction=(
        "You will receive 'summary_output' which can either be a real markdown or a guardrail message.\n"
        "If it's a guardrail message, DO NOT translate it — output as-is.\n\n"
        f"Otherwise, translate the markdown text into **{TARGET_LANGUAGE}** "
        "(ISO 639-1 code), preserving all markdown structure.\n"
    ),
    output_key="translated_text",
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)

# 5. Email Agent (unchanged)
email_agent = LlmAgent(
    name="EmailNotificationAgent",
    model="gemini-2.5-flash-lite",
    instruction="""
    Compose a concise HTML email using state variable {translated_text}.

Steps:
1) Subject: if state{translated_text} exists, start with it; max 90 chars.
2) Body:
   - brief intro + 3-5 bullets distilled from (translated_text) for each news article (convert Markdown to HTML bullets).
   - for all articles, If any URL appears, add 'Read more:' with the URL, after that all respective articles
3) Call send_email_smtp(
   to_addr=vidhika.mangla.22cse@bmu.edu.in,
   subject=subject,
   html_body=html
)

Return only the tool's string ('OK' or 'ERROR: ...').
""",
    tools=[send_email_smtp],
    output_key="email_status",
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
)

# --- Root Agent: Sequential Pipeline with Parallel Analysis ---
# Note: We can run scraper and analysis in parallel or sequentially
# Here's a sequential version with optional analysis

root_agent = SequentialAgent(
    name="NewsPipeline",
    sub_agents=[
        scraper_agent,
        crewai_analyzer_agent,  #A2A integration
        summariser_agent,
        multilingual_agent,
        email_agent
    ],
    description=(
        "News pipeline: "
        "Fetch → Analyze with CrewAI → Summarize → Translate → Email"
    )
)

# --- Async Agent Creation (for MCP Tools) ---
async def get__agent_async():
    """
    Creates the enhanced agent with MCP tools
    Use this when you want to consume tools from YOUR OWN MCP server
    """
    # Absolute path to your MCP server
    mcp_server_path = os.path.abspath(MCP_SERVER_PATH)
    
    # Create MCP Toolset that connects to your own MCP server
    mcp_toolset = MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command='python3',
                args=[mcp_server_path],
            ),
        ),
        # Optional: filter specific tools
        # tool_filter=['get_national_news_mcp', 'get_sports_news_mcp']
    )
    
    # Create an agent that uses MCP tools (optional - for testing MCP integration)
    mcp_consumer_agent = LlmAgent(
        model="gemini-2.5-flash-lite",
        name="mcp_consumer_agent",
        instruction="Use MCP tools to fetch news from the MCP server.",
        description="Consumes news via MCP protocol",
        tools=[mcp_toolset],
        output_key="mcp_output"
    )
    
    return mcp_consumer_agent, mcp_toolset

__all__ = ['root_agent', 'get_agent_async']