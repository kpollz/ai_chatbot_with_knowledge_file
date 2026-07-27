"""The compiled graph.

Nothing supplies a checkpointer here — unlike the ``langgraph dev`` route, where
the server provides one — so ``main.py`` attaches a Postgres one at startup.
"""

from langgraph.prebuilt import create_react_agent

from src.llm import get_chat_model
from src.prompts import SYSTEM_PROMPT
from src.tools import TOOLS

# Max tool-using steps before LangGraph stops. main.py turns this into the run's
# recursion_limit (2*N + 1: each step is a model call plus a tool call).
MAX_ITERATIONS = 3

graph = create_react_agent(
    model=get_chat_model(),
    tools=TOOLS,
    prompt=SYSTEM_PROMPT,
)
