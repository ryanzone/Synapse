# Synapse

**An open-source agentic AI backend built with Python and FastAPI.**

Synapse is not a chatbot. It is a goal-oriented execution engine — a backend system that receives a user goal, retrieves relevant context from semantic memory, plans a course of action, executes tools, reflects on results, and returns a natural language response.

It is designed to be modular, extensible, and self-improving over time through its reflection loop.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Setup](#local-setup)
  - [Environment Variables](#environment-variables)
  - [Docker Setup](#docker-setup)
- [API Reference](#api-reference)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Most AI backends are stateless request-response pipelines. Synapse takes a different approach: every user message is treated as a **goal** that passes through a structured agent cycle before a response is generated.

This makes Synapse suitable for use cases that require reasoning, tool use, memory, and multi-step task execution — rather than simple prompt-and-reply patterns.

> **Note:** Synapse is an early-stage project. It is not a general-purpose autonomous agent and does not claim to be. It is a structured, goal-oriented backend that currently supports planning, semantic memory, modular tool execution, reflection, and n8n workflow integration.

---

## Architecture

Synapse follows a linear agent pipeline on every request:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Synapse Agent Loop                        │
│                                                                 │
│   User Goal                                                     │
│       │                                                         │
│       ▼                                                         │
│   Semantic Memory Retrieval  ──►  Qdrant Vector Store           │
│       │                                                         │
│       ▼                                                         │
│   Planning Module  ──────────►  LM Studio (Local LLM)          │
│       │                                                         │
│       ▼                                                         │
│   Tool Execution  ───────────►  Tool Registry / n8n Workflows   │
│       │                                                         │
│       ▼                                                         │
│   Reflection Module  ────────►  Evaluates output quality        │
│       │                                                         │
│       ▼                                                         │
│   Natural Language Response                                     │
└─────────────────────────────────────────────────────────────────┘
```

Each stage is independently modular. Planning, memory, tool execution, and reflection can be extended or replaced without rewriting the core loop.

---

## Features

- **FastAPI REST API** — Async HTTP interface with clear, documented endpoints
- **Goal-Oriented Agent Cycle** — Structured pipeline from goal intake to response generation
- **Planning Module** — Decomposes goals into actionable steps via the local LLM
- **Long-Term Semantic Memory** — Stores and retrieves context using vector embeddings in Qdrant
- **Reflection Module** — Evaluates agent output and feeds observations back into the loop
- **Modular Tool Registry** — Register and invoke tools without modifying core agent logic
- **n8n Workflow Integration** — Trigger and monitor external automation workflows from within the agent cycle
- **Local LLM via LM Studio** — No external API dependency; runs entirely on-device
- **Docker Support** — Full containerised deployment with Docker Compose
- **Async Python Architecture** — Built for concurrency with `asyncio` and `uvicorn`
- **Pydantic v2 Models** — Strict, validated data contracts throughout the system

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| Data Validation | Pydantic v2 |
| AI Inference | LM Studio (local LLM) |
| Embeddings | Sentence Transformers |
| Vector Store | Qdrant |
| Automation | n8n |
| Infrastructure | Docker, Docker Compose |

---

## Project Structure

```
synapse/
├── app/
│   ├── main.py                  # FastAPI application entry point
│   ├── api/
│   │   ├── chat.py              # /chat endpoint
│   │   ├── memory.py            # /memory endpoints
│   │   └── workflow.py          # /workflow endpoints
│   ├── agent/
│   │   ├── cycle.py             # Core agent loop
│   │   ├── planner.py           # Planning module
│   │   └── reflection.py        # Reflection module
│   ├── memory/
│   │   ├── store.py             # Memory write operations
│   │   ├── search.py            # Semantic search
│   │   └── embeddings.py        # Sentence Transformer wrapper
│   ├── tools/
│   │   ├── registry.py          # Tool registration and dispatch
│   │   └── base.py              # Base tool interface
│   ├── workflows/
│   │   └── n8n_client.py        # n8n HTTP client
│   ├── models/
│   │   └── schemas.py           # Pydantic models
│   └── config.py                # Environment configuration
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- [LM Studio](https://lmstudio.ai/) installed and running a local model on `http://localhost:1234`
- [Qdrant](https://qdrant.tech/) running locally or via Docker
- [n8n](https://n8n.io/) (optional, required for workflow features)
- Docker and Docker Compose (optional, for containerised setup)

---

### Local Setup

**1. Clone the repository**

```bash
git clone https://github.com/your-username/synapse.git
cd synapse
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Configure environment variables**

```bash
cp .env.example .env
# Edit .env with your configuration (see Environment Variables below)
```

**5. Start the server**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.  
Interactive docs are at `http://localhost:8000/docs`.

---

### Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```env
# LM Studio
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=your-model-name

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=synapse_memory

# Embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2

# n8n (optional)
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your-n8n-api-key

# App
APP_ENV=development
LOG_LEVEL=info
```

---

### Docker Setup

The included `docker-compose.yml` brings up Synapse, Qdrant, and n8n together.

**Start all services**

```bash
docker-compose up --build
```

**Start only Synapse and Qdrant (without n8n)**

```bash
docker-compose up --build synapse qdrant
```

**Stop all services**

```bash
docker-compose down
```

> LM Studio runs on the host machine and is not managed by Docker Compose. Ensure it is running before starting containers, and that `LM_STUDIO_BASE_URL` points to your host machine's address (e.g., `http://host.docker.internal:1234/v1` on macOS/Windows).

---

## API Reference

### Core

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Root endpoint, returns project info |
| `GET` | `/health` | Health check for the service and dependencies |

### Chat

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chat` | Submit a user goal and receive an agent response |

**Request body:**

```json
{
  "goal": "Summarise the latest notes about project Alpha and suggest next steps."
}
```

**Response:**

```json
{
  "response": "...",
  "plan": [...],
  "tools_used": [...],
  "reflection": "..."
}
```

---

### Memory

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/memory/store` | Store a text entry in semantic memory |
| `POST` | `/memory/search` | Search memory by semantic similarity |
| `GET` | `/memory/recent` | Retrieve the most recently stored memories |

**`POST /memory/store` request body:**

```json
{
  "content": "Project Alpha kickoff is scheduled for Monday.",
  "metadata": {
    "source": "notes",
    "tags": ["project-alpha"]
  }
}
```

**`POST /memory/search` request body:**

```json
{
  "query": "Project Alpha schedule",
  "top_k": 5
}
```

---

### Workflows

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/workflow/list` | List available n8n workflows |
| `POST` | `/workflow/run` | Trigger an n8n workflow by ID |
| `GET` | `/workflow/status/{execution_id}` | Check the status of a workflow execution |

**`POST /workflow/run` request body:**

```json
{
  "workflow_id": "abc123",
  "payload": {
    "key": "value"
  }
}
```

---

## Roadmap

The following capabilities are under consideration for future development:

- [ ] **Multi-step task execution** — Allow the agent to chain multiple tool calls within a single goal cycle
- [ ] **Persistent session context** — Maintain goal history and agent state across requests
- [ ] **Tool result caching** — Avoid redundant tool calls for identical inputs within a session
- [ ] **Web UI** — A minimal frontend for interacting with and monitoring the agent
- [ ] **Authentication** — API key or OAuth2-based access control
- [ ] **Streaming responses** — Stream agent output token-by-token via Server-Sent Events
- [ ] **Configurable agent personas** — Allow system-level instructions to shape agent behaviour per deployment
- [ ] **Evaluation framework** — Benchmark planning quality and reflection accuracy across tasks
- [ ] **Plugin system** — Standardised interface for community-contributed tools

---

## Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature-name`
3. Commit your changes: `git commit -m "feat: add your feature"`
4. Push to your fork: `git push origin feat/your-feature-name`
5. Open a pull request against `main`

Please keep pull requests focused and include a clear description of what was changed and why. For significant changes, open an issue first to discuss the approach.

**Commit message convention:** This project follows [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

---

## License

This project is licensed under the [MIT License](LICENSE).

---
