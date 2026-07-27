"""Workflow graph for the Machine Issue Solver agent.

The prompt, the ``search_issues`` tool and the LLM factory come from the
Streamlit sub-project so the agent has a single definition. Those modules use
flat imports, so their directory goes on the path first.

The FastAPI wrapper in ``main.py`` imports ``graph`` from here. Nothing supplies
a checkpointer for us — unlike the ``langgraph dev`` route, where the server
provides one — so ``main.py`` attaches a Postgres one at startup.
"""

import os
import sys

_CHATBOT_APP = os.path.join(os.path.dirname(__file__), "..", "..", "chatbot", "app")
if os.path.isdir(_CHATBOT_APP):
    sys.path.insert(0, _CHATBOT_APP)

from langgraph.prebuilt import create_react_agent

from graph import SYSTEM_PROMPT, TOOLS
from llm import get_chat_model

agent = create_react_agent(
    model=get_chat_model(),
    tools=TOOLS,
    prompt=SYSTEM_PROMPT,
)

graph = agent
