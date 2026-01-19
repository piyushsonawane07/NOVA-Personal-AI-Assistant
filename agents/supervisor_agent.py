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
from tools.superviser_agent_tools import schedule_event, manage_email, get_current_datetime
from main import model
from langgraph.types import Command
from langgraph.checkpoint.memory import InMemorySaver 

SUPERVISOR_PROMPT = (
    "You are a helpful personal assistant. "
    "You can schedule calendar events and send emails. "
    "Break down user requests into appropriate tool calls and coordinate the results. "
    "When a request involves multiple actions, use multiple tools in sequence.\n\n"
    "IMPORTANT: When the user mentions relative dates like 'tomorrow', 'next week', 'next Tuesday', "
    "'in 2 days', 'today', etc., you MUST:\n"
    "1. FIRST call get_current_datetime to get today's date\n"
    "2. Calculate the actual date from the current date (e.g., if today is 2025-01-18 and user says 'tomorrow', use 2025-01-19)\n"
    "3. THEN call schedule_event with the calculated date in your request\n\n"
    "Always resolve relative dates to absolute dates before scheduling."
)

supervisor_agent = create_agent(
    model,
    tools=[schedule_event, manage_email, get_current_datetime],
    system_prompt=SUPERVISOR_PROMPT,
    checkpointer=InMemorySaver(),
)

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from pyfiglet import Figlet

console = Console()

def _render_message(message) -> None:
    message_type = getattr(message, "type", None)
    if message_type not in {"ai", "assistant"}:
        return
    content = getattr(message, "content", None)
    if not content:
        return
    print(content)


# def show_banner():
#     width = 70  # total box width

#     title_str = "Welcome to NOVA - Your Personal Assistant 🚀"
#     padded_title = title_str.center(width - 2)  # -2 for │ │

#     console.print("\n")
#     console.print(Text("─" * width, style="orange1"))
#     console.print(Text("│", style="orange1") + Text(padded_title, style="bold orange1") + Text("│", style="orange1"))
#     console.print(Text("─" * width, style="orange1"))
#     console.print("\n")

#     fig = Figlet(font="doom")
#     big_text = fig.renderText("NOVA")
#     console.print(Text(big_text, style="bold orange1"))

#     console.print(Text("📅 Schedule events and find open slots.", style="grey70"))
#     console.print(Text("✉️ Draft and send emails with approval.", style="grey70"))
#     console.print(Text("Type 'exit' or 'quit' to end. 👋\n", style="grey70"))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

def show_nova_banner():
    console = Console()

    # Big pixel-style title (custom text)
    logo = Text('''
    ███╗   ██╗ ██████╗ ██╗   ██╗ █████╗ 
    ████╗  ██║██╔═══██╗██║   ██║██╔══██╗
    ██╔██╗ ██║██║   ██║██║   ██║███████║
    ██║╚██╗██║██║   ██║╚██╗ ██╔╝██╔══██║
    ██║ ╚████║╚██████╔╝ ╚████╔╝ ██║  ██║
    ╚═╝  ╚═══╝ ╚═════╝   ╚═══╝  ╚═╝  ╚═╝
    ''', style="bold orange1")
    subtitle = Text("Welcome to NOVA - Your Personal Assistant 🚀", style="bold white")

    features = Text()
    features.append("\n📅 ", style="bright_cyan")
    features.append("Schedule events on your calendar.\n", style="grey80")

    features.append("✉️ ", style="bright_cyan")
    features.append(" Draft and send emails.\n", style="grey80")

    features.append("\nType ", style="grey70")
    features.append("'exit'", style="bold yellow")
    features.append(" or ", style="grey70")
    features.append("'quit'", style="bold yellow")
    features.append(" to end. 👋", style="grey70")

    content = Align.center(
        Text("\n")
        + logo
        + Text("\n\n")
        + subtitle
        + Text("\n")
        + features
        + Text("\n")
    )

    # Main box
    console.print(
        Panel(
            content,
            border_style="grey50",
            padding=(1, 6),
        )
    )

if __name__ == "__main__":
    
    show_nova_banner()

    config = {"configurable": {"thread_id": "cli"}}

    while True:
        query = input("💬 > ").strip()
        if not query:
            continue
        if query.lower() in {"exit", "quit"}:
            break

        interrupts = []
        print("\n⏳ Working...\n")
        for step in supervisor_agent.stream(
            {"messages": [{"role": "user", "content": query}]},
            config,
        ):
            for update in step.values():
                if isinstance(update, dict):
                    if "__interrupt__" in update:
                        interrupts.extend(update["__interrupt__"])
                    for message in update.get("messages", []):
                        _render_message(message)
                else:
                    interrupts.append(update[0])

        while interrupts:
            resume = {}
            for interrupt_ in interrupts:
                print(f"\n🔒 Review required (id: {interrupt_.id})")
                decisions = []
                for request in interrupt_.value["action_requests"]:
                    print(f"{request['description']}\n")
                    choice = input("✅ Approve? [y/N]: ").strip().lower()
                    decision_type = "approve" if choice in {"y", "yes"} else "reject"
                    decisions.append({"type": decision_type})
                resume[interrupt_.id] = {"decisions": decisions}

            interrupts = []
            for step in supervisor_agent.stream(
                Command(resume=resume),
                config,
            ):
                for update in step.values():
                    if isinstance(update, dict):
                        if "__interrupt__" in update:
                            interrupts.extend(update["__interrupt__"])
                        for message in update.get("messages", []):
                            _render_message(message)
                    else:
                        interrupts.append(update[0])