from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import google_search
from google.adk.agents.llm_agent import Agent
import os

GEMINI_MODEL = "gemini-2.5-flash"
import smtplib
from email.mime.text import MIMEText

def send_email_smtp(to_addr: str, subject: str, html_body: str) -> str:
    ""
    # SMTP configuration for sending OTP emails
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 587
    SMTP_USER = os.environ.get('SMTP_USER')
    SMTP_PASSWORD = os.environ.get('SMTP_PASS')
    from_addr = 'vidhikamangla@gmail.com'

    msg = MIMEText(f'Your OTP code is:')
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addr
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        return f"ERROR: {e}"
    
# ----------------------------
# Agent 1: Topic Asking + Info Retrieval Agent
# ----------------------------
topic_info_agent = LlmAgent(
    name="TopicInfoAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are an assistant that asks the user for a topic they want to learn about.
    Once the topic is provided, use google_search to fetch up-to-date information about it.

    Steps:
    1. Ask the user: 'What topic would you like to learn about today?'
    2. Once the user provides a topic, use google_search to gather concise, accurate, and factual information.
    3. Summarize the information clearly in Markdown format with headings, lists, and short paragraphs.

    Output policy:
    - Return only the summarized Markdown content.
    - Do not include personal opinions, filler phrases, or conversational text.
    - Write the final output to the session state key 'source_text'.
    """,
    tools=[google_search],
    output_key="source_text"
)

# ----------------------------
# Agent 2: Multilingual Translator Agent
# ----------------------------
multilingual_agent = LlmAgent(
    name="MultilingualTranslatorAgent",
    model=GEMINI_MODEL,
    instruction="""
    You are a multilingual translator for a study/quiz pipeline. Translate the text found in the session state key 'source_text' into the language specified by 'target_lang', and write the translated output to the state key 'translated_text'.

    Hard requirements:
    - Preserve Markdown headings, lists, tables, inline code, and fenced code blocks without translating code tokens.
    - Do not translate URLs, file paths, code identifiers, or words inside backticks.
    - Preserve numbers, dates, and named entities appearing in double quotes exactly as-is.
    - Keep paragraph breaks and list structure unchanged.
    - If the source is empty or missing, write an empty string to 'translated_text'.

    Output policy:
    - Return ONLY the translated text (no preface, no explanations).
    - If 'target_lang' equals 'auto' or is unsupported, default to 'en'.

    Supported languages (ISO 639-1): en, hi, bn, mr, pa, ta, te, kn, ml, gu, or, ur.
    """,
    output_key="translated_text"
)
# -------------------------------------------------------------------------
# 3. email Agent
# ------------------------------------------------------------------------

email_agent = LlmAgent(
    name="EmailNotificationAgent",
    model=GEMINI_MODEL,
    instruction="""
Compose a concise email about the {translated_text} Inputs from state amd send to address as given by the user 
Requirements:
- Subject <= 90 chars. Put the most important topic first.
- Body: short HTML with 3-5 bullets, each 1 line.
- Include a 'Read more' line if there is a URL in state.
- If content is missing, say 'No new updates.'
Then call send_email_smtp(to_addr, subject, html_body)
Return only 'OK' or 'ERROR: ...' from the call.
""",
    tools=[send_email_smtp],
    output_key="email_status"
)

# ----------------------------
# Root Sequential Agent (Pipeline)
# ----------------------------
root_agent = Agent(
    model=GEMINI_MODEL,
    name="RootAgent",
    description="""A helpful assistant that:
    1. Asks the user for a topic.
    2. Uses google search to find information.
    3. Then asks the user for a target language.
    4. Uses the multilingual agent to translate the info into that language.
    """,
    sub_agents=[topic_info_agent, multilingual_agent, email_agent],
    instruction="""You are a study assistant. The workflow is:
    1. Ask the user for a topic they want to know about.
    2. Use google search to summarize the topic. output just the markdown file for that topic summary.
    3. Ask the user which language they want the explanation in.
    4. Pass the gathered info to the multilingual agent to translate.
    5. return the translated summary and ask the user for their email address to send them that translated text.
    use email agent for that.
    """
)