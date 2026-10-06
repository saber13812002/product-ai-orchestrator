import os

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai.chat import OpenAIChat
from agno.os import AgentOS

# Model: default stays gpt-4o. Next step (LiteLLM on 52) is done purely via env:
#   OPENAI_API_KEY  -> the LiteLLM master/virtual key
#   OPENAI_BASE_URL -> e.g. http://172.20.1.52:4000/v1
# A placeholder key keeps the app bootable (health/docs/agents) before a real key is set.
model = OpenAIChat(
    id=(os.getenv("AGENT_MODEL_ID") or "gpt-4o"),
    api_key=(os.getenv("OPENAI_API_KEY") or "sk-placeholder-not-set"),
    base_url=(os.getenv("OPENAI_BASE_URL") or None),
)

agent = Agent(
    name="personal_agent",
    model=model,
    instructions="You are a helpful personal assistant.",
    markdown=True,
    add_datetime_to_context=True,
)

# Persist SQLite in /data so it survives container restarts (volume-mounted).
DB_FILE = os.path.join(os.getenv("DATA_DIR", "/data"), "agent.db")
agent_os = AgentOS(id="personal_agent", db=SqliteDb(db_file=DB_FILE), agents=[agent])
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve("personal_agent:app", host="0.0.0.0", port=7777, reload=False)
