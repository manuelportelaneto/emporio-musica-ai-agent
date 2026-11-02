# AGENT: PROJECT INITIALIZATION DIRECTIVE

You are an expert AI Engineer, Full-Stack Developer, and Cloud Architect.
Your mission is to autonomously build, test, and document the complete **Empório da Música Conversational AI Agent** for the Artefact Technical Case.

## 1. Operating Rules & Constraints

1. **Spec-Driven Execution:** Read and strictly follow every rule, contract, and interface specified in `SPEC.md`. Do not invent new tools or modify business policies.
2. **Context Documents in Root:** Note that original evaluation and business documents (`políticas_da_loja.pdf`, `Desafio_Técnico_AI_Engineer.pdf`, and data files) reside in the root or `data/` directories. Reference them accordingly.
3. **Primary Language:** Python 3.10+.
4. **Documentation Language:** Strict English for all code docstrings, README files, logs, and commit messages.
5. **Git Discipline:** Commit progress incrementally after each completed stage. Do not make a single giant commit. Follow conventional commit standards (e.g., `feat: setup data ingestion engine`, `test: add unit tests for catalog service`).
6. **Simplicity First:** Avoid unnecessary microservices or over-engineered distributed systems. Build a modular, clean, self-contained Python application.

## 2. Target Repository & Directory Layout

Repository: `https://github.com/manuelportelaneto/emporio-musica-ai-agent.git`

Expected repository structure:

```
emporio-musica-ai-agent/
├── data/
│   ├── categories.csv
│   ├── customers.csv
│   ├── order_items.csv
│   ├── orders.csv
│   ├── products.csv
│   ├── promotions.csv
│   └── políticas_da_loja.pdf
├── src/
│   ├── __init__.py
│   ├── config.py                 # Multi-provider LLM settings & environment
│   ├── data_engine.py            # CSV SQLite in-memory loader & RAG indexer
│   ├── guardrails/
│   │   ├── __init__.py
│   │   ├── input_guards.py       # Accessory interceptor & PII masking
│   │   └── output_guards.py      # Factual and persona validation
│   ├── services/
│   │   ├── __init__.py
│   │   ├── catalog_service.py    # Product & price lookups
│   │   ├── order_service.py      # Order tracking & CDC return calculation
│   │   └── policy_service.py     # RAG policy retrieval
│   ├── storage/
│   │   ├── __init__.py
│   │   └── audit_store.py        # Dual-layer SQLite persistence
│   ├── orchestrator.py           # Native tool-calling agent logic
│   └── cli.py                    # Rich CLI interface with Telemetry HUD
├── examples/
│   ├── scenario_1_catalog_search.md
│   ├── scenario_2_order_tracking.md
│   ├── scenario_3_return_policy_cdc.md
│   ├── scenario_4_accessory_refusal.md
│   └── scenario_5_out_of_scope.md
├── tests/
│   ├── test_services.py
│   └── test_guardrails.py
├── .env.example
├── .gitignore
├── README.md
├── SPEC.md
└── requirements.txt
```

## 3. Step-by-Step Execution Protocol

Execute and document the implementation in order:

### STEP 1: Foundation, Environment & Git Setup
* Create `.gitignore` (ignoring `.env`, `*.db`, `__pycache__`, `.pytest_cache`, vector cache).
* Create `requirements.txt` with locked versions (`langchain`, `langchain-community`, `groq`, `openai`, `pypdf`, `faiss-cpu` or `fastembed`, `rich`, `pydantic`, `pytest`).
* Create `.env.example` supporting Groq (default), OpenAI, and Ollama.
* Initialize Git repository and make initial commit: `chore: initial repository scaffolding and dependencies`.

### STEP 2: Data Ingestion & Backend Services
* Build `src/data_engine.py`: Loads CSVs into `:memory:` SQLite; parses `políticas_da_loja.pdf` into chunked vectors.
* Implement `src/services/catalog_service.py`: Parameterized queries with promotion joins and PIX discounts.
* Implement `src/services/order_service.py`: Computes 7-day CDC return eligibility deterministically.
* Implement `src/services/policy_service.py`: RAG search over policy chunks.
* Commit: `feat: implement SQLite data engine and deterministic backend services`.

### STEP 3: Multi-Layer Guardrails System
* Implement `src/guardrails/input_guards.py`: Intercepts accessories (strings, cables, picks, amps) without invoking the LLM; sanitizes PII.
* Implement `src/guardrails/output_guards.py`: Verifies factual consistency of prices and orders.
* Add unit tests in `tests/` and verify with `pytest`.
* Commit: `feat: implement input accessory guardrails and output verification`.

### STEP 4: Dual-Layer Persistence & Telemetry HUD
* Implement `src/storage/audit_store.py`: Creates `conversation_history` and `execution_audit_logs`.
* Instrument latency timers and token consumption metrics for every tool invocation.
* Commit: `feat: implement dual-layer persistence and telemetry tracking`.

### STEP 5: Agent Core & Native Tool Calling
* Build `src/config.py`: LLM factory returning Groq / OpenAI / Ollama instances.
* Build `src/orchestrator.py`: Binds tools (`lookup_catalog`, `get_order_details`, `query_store_policy`) using system prompt with the consultative selling persona and Campo Grande physical store invitation guidelines.
* Commit: `feat: implement conversational orchestrator with native tool calling`.

### STEP 6: Interactive Interface & Execution Examples
* Build `src/cli.py` using `rich`: Renders user messages, assistant responses, and a telemetry status footer (latency, tokens, tools executed).
* Run the 5 scenarios specified in `SPEC.md` and save the complete markdown transcripts in `examples/`.
* Commit: `feat: add Rich interactive CLI interface and real conversation scenarios`.

### STEP 7: Comprehensive README.md Generation
* Write an extensive, professional `README.md` in English including:
  1. **Project Overview & Architecture Diagram (Mermaid)**: Visualizing user flow, tools, and storage.
  2. **Engineering Methodology & Decisions**: Clear breakdown of the Spec-Driven approach, comparing decisions vs. alternatives and explaining objectives.
  3. **Step-by-step Setup & Quickstart Guide**: Prerequisites, environment variables configuration, and command to run the interactive CLI.
  4. **Telemetry & Dual-Layer Persistence**: Explanation of user conversation versus execution audit tables.
  5. **Guardrail Strategy**: Breakdown of the 3-layer safety system (including the accessory interceptor).
  6. **Known Limitations & Future Improvements Roadmap**: Detail the production evolution (Qdrant, Langfuse, WhatsApp Webhook, automated evals).
  7. **AI Assistant Transparency Statement**: Clear, professional disclosure of how coding assistants (Copilot, Cursor, etc.) were used in your workflow.
* Commit: `docs: generate comprehensive README and architectural documentation`.

Begin execution at **STEP 1**. Report completion of each stage before advancing.