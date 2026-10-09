import os

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai.chat import OpenAIChat
from agno.os import AgentOS

# Model: env-driven, resolved by workflow.config in ONE place (STEP 9.6).
# Mode A (external): LITELLM_BASE_URL + LITELLM_API_KEY (OPENAI_* still honored
# as a fallback); Mode B (bundled): the compose sidecar at http://litellm:4000/v1
# + LITELLM_MASTER_KEY. No mode-specific code here — a .env change suffices.
# A placeholder key keeps the app bootable (health/docs/agents) before a real key is set.
from workflow import config as _config

_LITELLM_BASE_URL, _LITELLM_API_KEY = _config.resolve_endpoint()
model = OpenAIChat(
    id=(os.getenv("AGENT_MODEL_ID") or "gpt-4o"),
    api_key=(_LITELLM_API_KEY or "sk-placeholder-not-set"),
    base_url=(_LITELLM_BASE_URL or None),
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
