from google.adk.models.llm_response import LlmResponse
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from typing import Optional, Set, Dict, Any
from google.adk.models.llm_request import LlmRequest

from google.genai import types
from google.genai import types as genai_types  

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
