"""The compiled graph, for the AG-UI server in ``main.py``.

Prompt, tools and the LLM factory come from the modules beside this one.

Nothing supplies a checkpointer here — unlike the ``langgraph dev`` route, where
the server provides one — so ``main.py`` attaches a Postgres one at startup.
"""

from langgraph.prebuilt import create_react_agent

from graph import SYSTEM_PROMPT, TOOLS
from llm import get_chat_model

agent = create_react_agent(
    model=get_chat_model(),
    tools=TOOLS,
    prompt=SYSTEM_PROMPT,
)

graph = agent
