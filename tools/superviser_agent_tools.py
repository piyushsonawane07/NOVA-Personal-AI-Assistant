import sys
from pathlib import Path

# Add project root to path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain.tools import tool
from agents.calander_agent import calendar_agent
from agents.email_agent import email_agent
from tools.tools import get_current_datetime  # Re-export from tools.py
from langchain.tools import tool, ToolRuntime


@tool
def schedule_event(request: str, runtime: ToolRuntime) -> str:
    """Schedule calendar events using natural language."""
    original_user_message = next(
        message for message in runtime.state["messages"]
        if message.type == "human"
    )
    prompt = (
        "You are assisting with the following user inquiry:\n\n"
        f"{original_user_message.text}\n\n"
        "You are tasked with the following sub-request:\n\n"
        f"{request}"
    )
    result = calendar_agent.invoke({
        "messages": [{"role": "user", "content": prompt}]
    })
    return result["messages"][-1].text


@tool
def manage_email(request: str) -> str:
    """Send emails using natural language."""
    result = email_agent.invoke({
        "messages": [{"role": "user", "content": request}]
    })
    return result["messages"][-1].text