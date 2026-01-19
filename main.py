from dotenv import load_dotenv
import os
import runpy
import typer

from langchain.chat_models import init_chat_model
from langchain_ollama import ChatOllama

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

model = init_chat_model(model="gpt-4o-mini", temperature=0)

ollama_model = ChatOllama(model="gemma3:latest", temperature=0, validate_model_on_init=True)


app = typer.Typer(help="Personal Assistant CLI")


@app.command()
def run(
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable Google debug logs.",
    ),
) -> None:
    os.environ["GOOGLE_DEBUG"] = "true" if debug else "false"
    runpy.run_module("agents.supervisor_agent", run_name="__main__")


if __name__ == "__main__":
    app()
