import sys
from pathlib import Path

# Add project root to path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain.agents import create_agent
try:
    from pyfiglet import figlet_format
except ImportError:  # pragma: no cover - optional dependency
    figlet_format = None

try:
    from rich.console import Console
    from rich.text import Text
except ImportError:  # pragma: no cover - optional dependency
    Console = None
    Text = None
from tools.tools import create_calendar_event, get_available_time_slots, get_current_datetime
from main import model
from langchain.agents.middleware import HumanInTheLoopMiddleware 
from langgraph.types import Command
from langgraph.checkpoint.memory import InMemorySaver 

CALENDAR_AGENT_PROMPT = (
    "You are a calendar scheduling assistant. "
    "Parse natural language scheduling requests (e.g., 'next Tuesday at 2pm') "
    "into proper ISO datetime formats.\n\n"
    "IMPORTANT: When the request contains relative dates like 'tomorrow', 'next Tuesday', "
    "'next week', 'today', 'in 3 days', etc., you MUST:\n"
    "1. FIRST call get_current_datetime to get the current date\n"
    "2. Calculate the exact date based on the current date\n"
    "3. Use that calculated date for scheduling\n\n"
    "ALWAYS check availability before scheduling:\n"
    "1. Call get_available_time_slots with the request date and duration\n"
    "2. The tool returns times in the user's timezone; prefer the requested time if listed\n"
    "3. If the requested time is not available, propose 2-3 open slots\n"
    "3. If the request is outside working hours (default 09:00-17:00), "
    "explain the hours and ask for a time within the window\n"
    "4. Only call create_calendar_event after the user confirms a slot\n\n"
    "Use create_calendar_event to schedule events. "
    "Always confirm what was scheduled in your final response."
)

calendar_agent = create_agent(
    model,
    tools=[create_calendar_event, get_available_time_slots, get_current_datetime],
    system_prompt=CALENDAR_AGENT_PROMPT,
    middleware=[ 
        HumanInTheLoopMiddleware( 
            interrupt_on={"create_calendar_event": True}, 
            description_prefix="Calendar event pending approval", 
        ), 
    ], 
    checkpointer=InMemorySaver(),
)

def _render_message(message) -> None:
    message_type = getattr(message, "type", None)
    if message_type not in {"ai", "assistant"}:
        return
    content = getattr(message, "content", None)
    if not content:
        return
    print(content)

if __name__ == "__main__":
    console = Console() if Console else None
    title = "Personal Assistant"
    subtitle = "Welcome to Personal Assistant"
    if figlet_format:
        banner = figlet_format(title)
    else:
        banner = title
    if console and Text:
        console.print(Text(subtitle, style="bold #FFA500"))
        console.print(Text(banner, style="bold #FFA500"))
    else:
        print(subtitle)
        print(banner)
    print("Calendar mode")
    print("Schedule or check availability.")
    print("Commands: exit, quit")
    print("-" * 40)

    while True:
        query = input("> ").strip()
        if not query:
            continue
        if query.lower() in {"exit", "quit"}:
            break

        config = {"configurable": {"thread_id": "calendar-cli"}}
        interrupts = []
        print("\nWorking...\n")
        result = calendar_agent.stream(
            {"messages": [{"role": "user", "content": query}]},
            config,
            stream_mode="values",
        )
        for step in result:
            if "__interrupt__" in step:
                interrupts.extend(step["__interrupt__"])
            for message in step.get("messages", []):
                _render_message(message)
            print("\n")

        while interrupts:
            resume = {}
            for interrupt_ in interrupts:
                print(f"\nReview required (id: {interrupt_.id})")
                decisions = []
                for request in interrupt_.value["action_requests"]:
                    print(f"{request['description']}\n")
                    choice = input("Approve? [y/N]: ").strip().lower()
                    decision_type = "approve" if choice in {"y", "yes"} else "reject"
                    decisions.append({"type": decision_type})
                resume[interrupt_.id] = {"decisions": decisions}

            interrupts = []
            for step in calendar_agent.stream(
                Command(resume=resume),
                config,
                stream_mode="values",
            ):
                if "__interrupt__" in step:
                    interrupts.extend(step["__interrupt__"])
                for message in step.get("messages", []):
                    _render_message(message)
                print("\n")