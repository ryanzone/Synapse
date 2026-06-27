# Synapse — Architecture Diagrams

> Enterprise-grade architecture documentation for the Synapse autonomous AI agent platform.

---

## 1. High-Level System Architecture

```mermaid
graph TB
    subgraph CLIENT["Client Layer"]
        UI["HTTP Client"]
        WS["WebSocket Client"]
    end

    subgraph API["API Gateway — FastAPI"]
        REST["REST API<br/>/v1/agent"]
        WSAPI["WebSocket API<br/>/v1/ws"]
    end

    subgraph AGENT["Agent Runtime"]
        AC["Agent Cycle"]
        PL["Planner"]
        EX["Executor"]
        RE["Reflection Engine"]
        CB["Context Builder"]
    end

    subgraph MEMORY["Memory Layer"]
        MS["Memory Service"]
        ES["Embedding Service"]
        QD[("Qdrant<br/>Vector Store")]
    end

    subgraph TOOLS["Tool Layer"]
        TR["Tool Registry"]
        BI["Built-in Tools"]
        WC["Workflow Client"]
    end

    subgraph INFERENCE["Inference Layer"]
        LM["LM Studio<br/>OpenAI-Compatible API"]
        QW["Qwen3 Model"]
    end

    subgraph ORCHESTRATION["Workflow Orchestration"]
        N8N["n8n<br/>Workflow Engine"]
    end

    UI --> REST
    WS --> WSAPI
    REST --> AC
    WSAPI --> AC
    AC --> CB
    AC --> PL
    AC --> EX
    AC --> RE
    CB --> MS
    PL --> LM
    EX --> TR
    RE --> LM
    MS --> ES
    MS --> QD
    ES --> QD
    TR --> BI
    TR --> WC
    WC --> N8N
    LM --> QW
```

---

## 2. Component Architecture

```mermaid
graph LR
    subgraph API["api/"]
        R["routes.py"]
        WH["websocket_handler.py"]
        M["middleware.py"]
    end

    subgraph CORE["core/"]
        AC["agent_cycle.py"]
        PL["planner.py"]
        EX["executor.py"]
        RE["reflection.py"]
        CB["context_builder.py"]
    end

    subgraph TOOLS["tools/"]
        TR["tool_registry.py"]
        BI["builtin_tools.py"]
        WC["workflow_client.py"]
    end

    subgraph MEMORY["memory/"]
        MS["memory_service.py"]
        ES["embedding_service.py"]
        QC["qdrant_client.py"]
    end

    subgraph INFRA["infrastructure/"]
        LC["llm_client.py"]
        CFG["config.py"]
        LOG["logger.py"]
    end

    R --> AC
    WH --> AC
    AC --> PL
    AC --> EX
    AC --> RE
    AC --> CB
    CB --> MS
    PL --> LC
    EX --> TR
    RE --> LC
    TR --> BI
    TR --> WC
    MS --> ES
    MS --> QC
    ES --> QC
    R --> M
    WH --> M
    AC --> LOG
    LC --> CFG
    QC --> CFG
```

---

## 3. Autonomous Agent Workflow

```mermaid
flowchart TD
    OBS["Observe\nReceive user request and session context"]
    RET["Retrieve\nSemantic search over long-term memory"]
    CTX["Build Context\nAssemble retrieved memory + conversation history"]
    PLAN["Plan\nLLM generates structured action plan"]
    EXEC["Execute\nDispatch tools and workflows"]
    REFLECT["Reflect\nEvaluate outputs, detect failures, self-correct"]
    STORE["Store\nPersist experience to vector memory"]
    RESP["Respond\nStream final answer to client"]

    DONE{{"Terminal?"}}

    OBS --> RET
    RET --> CTX
    CTX --> PLAN
    PLAN --> EXEC
    EXEC --> REFLECT
    REFLECT --> DONE
    DONE -- "Needs retry" --> PLAN
    DONE -- "Complete" --> STORE
    STORE --> RESP
```

---

## 4. Request Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant F as FastAPI
    participant M as Middleware
    participant AC as Agent Cycle
    participant CB as Context Builder
    participant PL as Planner
    participant EX as Executor
    participant RE as Reflection Engine
    participant MS as Memory Service
    participant LM as LM Studio

    C->>F: POST /v1/agent {prompt, session_id}
    F->>M: Validate request, inject trace_id
    M->>AC: AgentRequest(prompt, session_id)
    AC->>MS: retrieve(prompt, top_k=5)
    MS-->>AC: MemoryChunks[]
    AC->>CB: build(prompt, chunks, history)
    CB-->>AC: ContextObject
    AC->>PL: plan(context)
    PL->>LM: POST /v1/chat/completions
    LM-->>PL: ActionPlan
    PL-->>AC: ActionPlan
    AC->>EX: execute(plan)
    EX-->>AC: ToolResults[]
    AC->>RE: reflect(plan, results)
    RE->>LM: POST /v1/chat/completions
    LM-->>RE: ReflectionReport
    RE-->>AC: ReflectionReport
    AC->>MS: store(experience)
    AC-->>F: AgentResponse
    F-->>C: 200 OK {response, trace_id}
```

---

## 5. Memory Architecture

```mermaid
graph TB
    subgraph INGEST["Ingestion Pipeline"]
        RAW["Raw Text / Experience"]
        CHUNK["Chunking Strategy<br/>Fixed / Semantic / Sentence"]
        EMB["Sentence Transformers<br/>all-MiniLM-L6-v2"]
        VEC["Dense Vector<br/>384 dimensions"]
    end

    subgraph STORAGE["Vector Storage — Qdrant"]
        COL[("Collection<br/>synapse_memory")]
        IDX["HNSW Index<br/>ef=128, m=16"]
        PAY["Payload Store<br/>metadata, timestamp, session_id"]
    end

    subgraph RETRIEVAL["Retrieval Pipeline"]
        QUERY["Query Embedding"]
        ANN["Approximate Nearest Neighbour<br/>cosine similarity"]
        RANK["Re-ranking<br/>recency + relevance score"]
        TOP["Top-K Results<br/>default k=5"]
    end

    subgraph CONSUMER["Memory Consumer"]
        CB["Context Builder"]
        RE["Reflection Engine"]
    end

    RAW --> CHUNK
    CHUNK --> EMB
    EMB --> VEC
    VEC --> COL
    COL --> IDX
    COL --> PAY

    CB --> QUERY
    RE --> QUERY
    QUERY --> ANN
    ANN --> IDX
    ANN --> RANK
    RANK --> TOP
    TOP --> CB
    TOP --> RE
```

---

## 6. Tool Execution Flow

```mermaid
flowchart TD
    PLAN["Planner\nProduces structured ActionPlan\nwith tool_name and parameters"]

    TR["Tool Registry\nResolves tool_name to handler\nValidates parameter schema"]

    subgraph BUILT["Built-in Tools"]
        WEB["web_search"]
        CODE["code_executor"]
        FILE["file_reader"]
        CALC["calculator"]
        HTTP["http_request"]
    end

    subgraph WORKFLOW["n8n Workflows"]
        WC["Workflow Client\nHTTP POST to n8n webhook"]
        WF1["Notification Workflow"]
        WF2["Data Pipeline Workflow"]
        WF3["Integration Workflow"]
    end

    AGG["Result Aggregator\nCollect outputs from all tool calls"]
    RE["Reflection Engine\nEvaluate tool results"]

    PLAN --> TR
    TR --> BUILT
    TR --> WC
    WC --> WF1
    WC --> WF2
    WC --> WF3
    BUILT --> AGG
    WF1 --> AGG
    WF2 --> AGG
    WF3 --> AGG
    AGG --> RE
```

---

## 7. Deployment Architecture

```mermaid
graph TB
    USER["User / Browser"]

    subgraph DOCKER["Docker Network — synapse_net"]
        subgraph APP["synapse-api  :8000"]
            FA["FastAPI Application"]
            AC["Agent Runtime"]
        end

        subgraph QDRANT_SVC["qdrant  :6333"]
            QD[("Qdrant\nVector Database")]
            QVOL[("Volume: qdrant_data")]
        end

        subgraph N8N_SVC["n8n  :5678"]
            N8["n8n\nWorkflow Engine"]
            NVOL[("Volume: n8n_data")]
        end

        subgraph LMS["lmstudio  :1234"]
            LM["LM Studio\nInference Server"]
            MODEL["Qwen3 Model\n(host GPU / CPU)"]
        end
    end

    ENV[(".env\nSecrets & Config")]

    USER -->|"HTTPS :443 / :8000"| FA
    FA --> AC
    AC -->|"REST :6333"| QD
    AC -->|"REST :5678"| N8
    AC -->|"OpenAI API :1234"| LM
    LM --> MODEL
    QD --- QVOL
    N8 --- NVOL
    ENV -.->|"environment"| APP
```

---

## 8. Sequence Diagram — Full Agent Interaction

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant API as FastAPI
    participant A as Agent Cycle
    participant MEM as Memory Service
    participant LLM as LM Studio
    participant TOOL as Tool Executor
    participant REF as Reflection Engine

    U->>API: Submit prompt
    API->>A: Dispatch AgentRequest

    A->>MEM: Retrieve relevant memories
    MEM-->>A: MemoryChunks[]

    A->>LLM: Generate action plan (context + prompt)
    LLM-->>A: Structured ActionPlan

    loop For each action in plan
        A->>TOOL: Execute tool call
        TOOL-->>A: ToolResult
    end

    A->>REF: Evaluate plan vs results
    REF->>LLM: Reflection prompt
    LLM-->>REF: Self-critique + corrections

    alt Reflection triggers retry
        REF-->>A: Retry with corrections
        A->>LLM: Revised plan
        LLM-->>A: Updated ActionPlan
    end

    A->>MEM: Store experience embedding
    MEM-->>A: ACK

    A-->>API: AgentResponse
    API-->>U: Final response
```

---

## 9. Project Dependency Graph

```mermaid
graph TD
    CFG["config.py"]
    LOG["logger.py"]
    LC["llm_client.py"]
    ES["embedding_service.py"]
    QC["qdrant_client.py"]
    MS["memory_service.py"]
    TR["tool_registry.py"]
    BI["builtin_tools.py"]
    WC["workflow_client.py"]
    CB["context_builder.py"]
    PL["planner.py"]
    EX["executor.py"]
    RE["reflection.py"]
    AC["agent_cycle.py"]
    RT["routes.py"]
    WH["websocket_handler.py"]
    MW["middleware.py"]
    MAIN["main.py"]

    CFG --> LC
    CFG --> ES
    CFG --> QC
    CFG --> WC
    LOG --> AC
    LOG --> RT
    LC --> PL
    LC --> RE
    ES --> MS
    QC --> MS
    MS --> CB
    TR --> BI
    TR --> WC
    CB --> AC
    PL --> AC
    EX --> AC
    RE --> AC
    TR --> EX
    MW --> RT
    MW --> WH
    RT --> AC
    WH --> AC
    RT --> MAIN
    WH --> MAIN
    MW --> MAIN
```

---

## 10. Backend Package Structure

```mermaid
graph TD
    ROOT["synapse/"]

    subgraph SRC["src/"]
        subgraph API_PKG["api/"]
            ROUTES["routes.py"]
            WSH["websocket_handler.py"]
            MID["middleware.py"]
            SCHEMAS["schemas.py"]
        end

        subgraph CORE_PKG["core/"]
            AGENTC["agent_cycle.py"]
            PLANR["planner.py"]
            EXECR["executor.py"]
            REFLR["reflection.py"]
            CTXB["context_builder.py"]
        end

        subgraph TOOLS_PKG["tools/"]
            TREG["tool_registry.py"]
            BTOOLS["builtin_tools.py"]
            WCLIENT["workflow_client.py"]
        end

        subgraph MEM_PKG["memory/"]
            MEMSVC["memory_service.py"]
            EMBSVC["embedding_service.py"]
            QDCLI["qdrant_client.py"]
            MODELS["models.py"]
        end

        subgraph INFRA_PKG["infrastructure/"]
            LLMCLI["llm_client.py"]
            CONFG["config.py"]
            LOGG["logger.py"]
        end

        MAINPY["main.py"]
    end

    subgraph DEPLOY["deployment/"]
        DC["docker-compose.yml"]
        DF["Dockerfile"]
        ENV[".env.example"]
    end

    subgraph TESTS["tests/"]
        TCORE["test_core/"]
        TMEM["test_memory/"]
        TTOOLS["test_tools/"]
    end

    ROOT --> SRC
    ROOT --> DEPLOY
    ROOT --> TESTS
```

---

*Generated for the Synapse autonomous AI agent platform.*
