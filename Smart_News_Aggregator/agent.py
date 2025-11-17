import datetime
import json
import logging
import asyncio
import uuid
import time
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
from google.adk.tools import google_search     

from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner

from google.adk.events import Event, EventActions

import os
from email.mime.text import MIMEText
import smtplib

from .Scrapers.entertainment_scraper import scrape_entertainment_top_n
from .Scrapers.sports_scraper import scrape_sports_top_n
from .Scrapers.international_scraper import scrape_international_top_n
from .Scrapers.national_scraper import scrape_national_top_n
from .Scrapers.states_scraper import scrape_states_top_n


STYLE_OF_WRITING = "sarcastic"
TARGET_LANGUAGE = "hi"  # ISO code, e.g. hi=Hindi, en=English, ta=Tamil


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
    "updates", "breaking", "tell me about", "what's new", "information"
}

VALID_STATES: Set[str] = {
    "mumbai", "delhi", "bengaluru", "kolkata", "chennai", "pune",
    "hyderabad", "ahmedabad", "maharashtra", "karnataka",
    "west bengal", "tamil nadu", "gujarat", "uttar pradesh",
    "rajasthan", "punjab", "kerala", "andhra pradesh", "goa"
}


# GUARDRAILS

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
    
    # msg = MIMEText("html_body", "html", "utf-8")
    # msg["Subject"] = "trial"
    # msg["From"] = FROM_ADDR
    # msg["To"] = "vidhika.mangla.22cse@bmu.edu.in"

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
        msg = "📰 I am a news assistant. I can only fetch news, headlines, and articles."
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
    before_tool_callback=tool_guardrail,
)

summariser_agent = LlmAgent(
    model="gemini-2.5-flash-lite",
    name="summariser_agent",
    description=f"Summarises scraped articles and writes in a {STYLE_OF_WRITING} tone.",
    instruction=(
        f"You will receive an essay OR a guardrail message.\n"
        "If input is a guardrail message (starts with !!! or 📰), just repeat it as-is.\n\n"
        f"Otherwise, write a **clean markdown news report** in a **{STYLE_OF_WRITING} tone**.\n\n"
        "CRITICAL RULES:\n"
        "• Output ONLY markdown.\n"
        "• For each article:\n"
        "   ## Title\n"
        "   Summary paragraph (120-160 words).\n"
        "• No bullet lists or prefaces.\n"
    ),
    output_key="summary_output",
)


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
)

email_agent = LlmAgent(
    name="EmailNotificationAgent",
    model="gemini-2.5-flash-lite",
    instruction="""
    Compose a concise HTML email using state variable {translated_text}.

Steps:
1) Subject: if state{translated_text} exists, start with it; max 90 chars.
2) Body:
   - brief intro + 3-5 bullets distilled from (translated_text) for each news article (convert Markdown to HTML bullets).
   - for all articles, If any URL appears, add 'Read more:' with the URL, after that all  respective articles
3) Call send_email_smtp(
   to_addr=sanya.goel.22cse@bmu.edu.in,
   subject=subject,
   html_body=html
)

Return only the tool's string ('OK' or 'ERROR: ...').
""",
    tools=[send_email_smtp],
    output_key="email_status"
)

root_agent = SequentialAgent(
    name="NewsPipeline",
    sub_agents=[scraper_agent, summariser_agent, multilingual_agent, email_agent],
    description=f"Fetch → Summarise → Translate (with guardrail awareness).-> send email"
)

async def main():
    session_service = InMemorySessionService()
    SESSION_ID = str(uuid.uuid4())
    USER_ID = "vid"
    APP_NAME = "SmartNewsAggregator"

    state_context = {"user": "Vidhika", "guardrail_output": None, "abort_pipeline": False}

    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state=state_context
    )

    print(f"Session ID: {session.id}")
    runner = Runner(agent=root_agent, session_service=session_service, app_name=APP_NAME)

    while True:
        user_input = input("\nYou > ")
        if user_input.lower() == "quit":
            break

        state = (await session_service.get_session(APP_NAME, USER_ID, SESSION_ID)).state
        input_text = state.get("guardrail_output") if state.get("abort_pipeline") else user_input

        user_message = types.Content(parts=[types.Part(text=input_text)])

        for event in runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=user_message):
            if event.content and event.content.parts:
                msg = event.content.parts[0].text
                print(f"\n🧩 Agent > {msg}\n")

                if event.is_final_response():
                    state_changes = {"guardrail_output": msg}
                    actions_with_update = EventActions(state_delta=state_changes)
                    system_event = Event(
                        invocation_id=str(uuid.uuid4()),
                        author="system",
                        actions=actions_with_update,
                        timestamp=time.time()
                    )
                    await session_service.append_event(session, system_event)

    final_session = await session_service.get_session(APP_NAME, USER_ID, SESSION_ID)
    print("\n🧾 Final Session State:\n", final_session.state)



if __name__ == "__main__":
    asyncio.run(main())