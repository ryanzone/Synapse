import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.agent.cycle import AgentCycle
from app.agent.tools import ToolRegistry
from app.core.llm_client import LLMClient
from app.core.memory import MemoryService
from app.agent.tools import build_default_registry

load_dotenv()

app = FastAPI(
    title="Synapse",
    version="1.0.0",
    description="Local Autonomous AI Agent"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Configuration
# -------------------------

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

LMSTUDIO_URL = os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "local-model")

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

# -------------------------
# Core Services
# -------------------------

memory = MemoryService(
    qdrant_url=QDRANT_URL,
    collection=os.getenv("QDRANT_COLLECTION", "synapse_memory"),
)

llm = LLMClient()

tools = build_default_registry()

engine = AgentCycle(
    memory=memory,
    llm=llm,
    tools=tools,
)

# -------------------------
# App State
# -------------------------

app.state.memory = memory
app.state.llm = llm
app.state.tools = tools
app.state.engine = engine

# -------------------------
# Routes
# -------------------------

app.include_router(router)

# -------------------------
# Health Check
# -------------------------
