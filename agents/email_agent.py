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
from tools.tools import send_email
from main import model
from langchain.agents.middleware import HumanInTheLoopMiddleware 
from langgraph.types import Command
from langgraph.checkpoint.memory import InMemorySaver 

EMAIL_AGENT_PROMPT = (
    "You are an email assistant. "
    "Compose professional emails based on natural language requests. "
    "Extract recipient information and craft appropriate subject lines and body text. "
    "Use send_email to send the message. "
    "Always confirm what was sent in your final response."
)

email_agent = create_agent(
    model,
    tools=[send_email],
    system_prompt=EMAIL_AGENT_PROMPT,
    middleware=[ 
        HumanInTheLoopMiddleware( 
            interrupt_on={"send_email": True}, 
            description_prefix="Outbound email pending approval", 
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
    config = {"configurable": {"thread_id": "email-cli"}}
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
    print("Email mode")
    print("Compose and send emails.")
    print("Commands: exit, quit")
    print("-" * 40)
    while True:
        query = input("> ").strip()
        if not query:
            continue
        if query.lower() in {"exit", "quit"}:
            break

        interrupts = []
        print("\nWorking...\n")
        for step in email_agent.stream(
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
                print(f"\nReview required (id: {interrupt_.id})")
                decisions = []
                for request in interrupt_.value["action_requests"]:
                    print(f"{request['description']}\n")
                    choice = input("Approve? [y/N]: ").strip().lower()
                    decision_type = "approve" if choice in {"y", "yes"} else "reject"
                    decisions.append({"type": decision_type})
                resume[interrupt_.id] = {"decisions": decisions}

            interrupts = []
            for step in email_agent.stream(
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