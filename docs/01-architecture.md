# ARCH-001 — Architecture Document — AI Clinic Booking Agent

| | |
|---|---|
| **Doc-ID** | ARCH-001 |
| **Project** | `ai-clinic-agent` |
| **Version** | 3.1 |
| **Status** | Draft |
| **Author** | TBD |
| **Approved-by** | TBD |
| **Date** | 2026-07-02 |
| **Style** | Modular Monolith · Multi-Agent (ADK) · Polyglot Persistence by data characteristics |

> This is a **design document** presenting the architectural approach; the scope is deliberately kept small to focus on design thinking and trade-offs. Major decisions are summarized in the table at [§11 — Decision Log](#decision-log) at the end of this document — each row states the *decision* and the *rationale*.

---

## 1. Architectural Drivers

The architecture is driven by the requirements in SRS-001:

| Driver | Source | Architectural consequence |
|--------|-------|------------------|
| Natural-language booking conversation with intent understanding | FR-01, FR-06 | Multi-Agent (ADK) is the *core*; one agent per domain, coordinated through an Orchestrator Agent. |
| **Grounded** FAQ/medical answers, no fabrication | FR-04, FR-05 | RAG (Qdrant) is the **single source of knowledge**; grounding plus an "not found" fallback are mandatory. |
| **No double-booking** even under concurrent requests | FR-03 | Transactional data lives in a DB with ACID + a unique constraint (PostgreSQL), not in a file. |
| Detect emergencies, respond with minimal safe guidance | FR-07 | A separate `Emergency Agent` with a fixed scope (no tools, no external system integration); two-layer detection — rule code in `app/webhook/handler.py` runs before ADK (primary), the `Orchestrator Agent` (LLM) catches indirect phrasing as a safety net (§5.4, ADR-0019). |
| Non-technical staff can self-administer | NFR Usability | Configuration data (doctors, hours, promotions, knowledge content) lives in Postgres, managed through internal CRUD screens (`modules/doctor`, `modules/knowledge`) — no Google Sheets (ADR-0016). |
| Self-hosted, portable, simple to operate | NFR Operability | The whole stack runs via `docker-compose`; not locked to a specific cloud; the backend is stateless. |
| Cloud API (Gemini) can fail or be slow | NFR Reliability | Retry/timeout wraps every LLM call in the tool layer. |

---

## 2. Design Philosophy: Multi-Agent Conversation as the Core

In terms of overall architectural style, this is still a **Modular Monolith** (§3–4) — a single deployable, clear module boundaries, not microservices. What differs from an ordinary CRUD modular monolith is that the **central domain is modeled around conversational intent** (multi-agent ADK), not around data tables — the system treats AI-driven conversation as the main axis, not a chatbot bolted onto CRUD. Specifically:

1. **The central domain is customer intent**, not a data table. The system splits agents by *intent type*: policy Q&A → symptom triage → book/reschedule → emergency.
2. **Designed for LLM uncertainty:** intent is classified explicitly by the `Orchestrator Agent`; every agent has a narrow tool scope; write operations (booking) always go through a DB constraint rather than trusting LLM output.
3. **Separating "knowledge to read" from "transactions to write":** RAG (Qdrant) serves **open knowledge with no absolute right/wrong** (policy, medical guidance, clinic operational info) — no separate context cache for knowledge, to avoid two sources drifting apart; PostgreSQL serves write-transactions that must be exactly correct. This principle runs throughout (see §6 and ADR-0002). **Two deliberate exceptions, for the same "small data + needs 100% visibility" reason:** (a) the symptom-to-specialty triage table is hard-enum logic that must be exactly correct — embedded directly in the system prompt (§6.2, ADR-0018); (b) the doctor roster is only a few dozen records — stored directly in the `doctors` table (Postgres) and rendered in full into the `Symptom Agent`'s context, bypassing Qdrant, to avoid retrieval-miss risk on listing/comparison questions (§6.3, ADR-0020).
4. **Emergency is an escape hatch, not a business flow:** the `Emergency Agent` has a fixed scope (a single static guidance message), calls no tools, integrates with no external system. Coordinating real medical response is out of scope for this AI system (ADR-0014).
5. **AI-oriented observability:** trace every step (intent classification → agent selection → tool call → result) to diagnose conversation quality, not just HTTP logs.

---

## 3. Architectural Style

### 3.1 Centrally-orchestrated Multi-Agent
A single deployable backend (FastAPI — simple to operate, fits the scope), containing an **ADK agent network** with one `Orchestrator Agent`. Each agent has a clear intent boundary and its own tool set; it can be split into an independent service later without rewriting logic (ADR-0001).

### 3.2 Agent + Tool + Data — 3 layers, not 2
Each agent splits into 2 internal layers, and **never touches data directly** — it must go through the dedicated `dal/` layer (§4):

```
        ┌─────────────────────────────────────────────────┐
        │  agent        (intent + orchestration)           │  ← ADK definition, prompt, routing
        │  orchestrator/agent.py · booking/agent.py · ...  │
        ├─────────────────────────────────────────────────┤
        │  tools        (calls down to dal/, NO raw SQL)   │  ← normalizes input, calls dal/, handles exceptions
        │  booking/tools.py · faq/tools.py · ...           │
        ├─────────────────────────────────────────────────┤
        │  dal/        (data-access layer — kept separate) │  ← holds SQL, Qdrant filters
        │  booking_repository.py · doctor_repository.py ·  │
        │  knowledge_repository.py · qdrant_client.py · ...│
        └─────────────────────────────────────────────────┘
```

Pure business rules (e.g., validating a slot, formatting a phone number) are split out as plain Python in `ai-agents/core/domain/`, testable without mocking the network. `tools` is kept separate from `dal/` so the tool layer only worries about "what to call, how to handle the error given the conversational context," while `dal/` worries about "write the query correctly, set the constraint correctly" — two different responsibilities, so changing one doesn't force changes to the other.

The `Emergency Agent` is a deliberate exception: **it has no `tools` layer** because it never calls `dal/` — its static response lives entirely in the prompt/agent layer.

**Why no Port/Adapter abstraction per provider:** the stack is already fixed (ADK + Qdrant + Postgres); adding an interface layer would just be boilerplate out of proportion to scope. Keeping `dal/` separate already captures most of the benefit of Port/Adapter (swapping a datastore only touches one place) without defining an abstract interface for every provider (ADR-0003). All configuration/knowledge that was originally planned for Google Sheets now lives in Postgres — there's no longer a third provider (ADR-0016).

---

## 4. Architectural Decomposition: 5 Clear Layers

The top-level organizing principle: **physically separate by rate of change and risk**, don't mix agents with CRUD, and don't let either open a direct connection to Postgres/Qdrant — all data access goes through one dedicated layer.

- **`ai-agents/`** — all AI reasoning/conversation: the Orchestrator Agent + 4 domain agents (booking, faq, symptom, emergency), prompts, base classes for agents/tools. This is the "brain," changing constantly as conversation quality is tuned.
- **`modules/`** — pure business logic, unrelated to AI: CRUD/API for admin screens (admin edits/cancels bookings, manages doctors, manages knowledge content) **+ the RAG ingestion pipeline** (`knowledge_ingestion`, runs in the background, not over HTTP). This is the "operational hands," stable, and would keep running even without AI.

`ai-agents/` and `modules/` are **peers** — both are coordinated directly by `app/`, neither sits inside or depends on the other.

- **`core/`** — CRUD base classes shared by `modules/` and `dal/` (**reused as-is from the `rag-health` project**, ADR-0021): `base_model.py`, `base_repository.py`, `base_service.py`, `base_response.py`, `exceptions.py`. Placed **at the root**, a peer of `ai-agents/`/`modules/`/`dal/`/`common/` — there's no more separate `modules/core` (merged in here). `ai-agents/core/` **remains separate** (base classes for agents/tools, not CRUD).
- **`dal/`** — the data-access layer, kept separate from `ai-agents/`/`modules/`: table-specific repositories (Postgres, inheriting `core/base_repository.py`), a client factory (Qdrant). This is the *only boundary* containing repositories that know real table/collection names (ADR-0013, clarified by ADR-0021).
- **`common/`** — cross-cutting infrastructure used system-wide: config, observability, resilience, the Gemini client (LLM/embedding) — not business data, so it doesn't belong in `dal/`.

Why `dal/` is kept separate (instead of putting the client in `common/` or scattering it across `ai-agents/*/tools.py` as in an earlier design): when swapping datastores (e.g., Postgres → another DB, or adding a cache), only `dal/` needs to change, instead of chasing down every tool in every agent. It's also the only place holding SQL statements/Qdrant filters — agent tools call `dal/` through an interface, never writing their own queries.

```
┌───────────────────────────────────────────────────────────────────┐
│  app/  (FastAPI — Composition Root, ADK runtime, webhook router)   │
└────────┬──────────────────────────────────────┬────────────────────┘
         │                                      │
┌────────▼─────────────────────────┐  ┌─────────▼─────────────────────┐
│  ai-agents/   (AI layer)          │  │  modules/  (business layer)    │
│                                   │  │                                │
│  orchestrator/ classifies intent,│  │  booking/                      │
│   transfers to child agent       │  │   admin CRUD for bookings       │
│  faq/         policy/clinic QA   │  │   (no agent involved)          │
│  symptom/     doctor suggestion  │  │  doctor/                       │
│  booking/     book/reschedule/   │  │   CRUD doctors + profile        │
│               cancel             │  │  knowledge/                    │
│  emergency/   static response    │  │   CRUD knowledge + publish      │
│                                   │  │  knowledge_ingestion/          │
│  core/  (base_agent, base_tool,  │  │   chunk + embed pipeline        │
│   prompt loader, AI exceptions)  │  │   (ADR-0021, no HTTP)          │
└────────┬──────────────────────────┘  └─────────┬───────────────────────┘
         │                                        │
         └──────────────────┬─────────────────────┘
                             ▼
┌───────────────────────────────────────────────────────────────────┐
│  core/  (base_model · base_repository · base_service ·             │
│          base_response · exceptions — reused from rag-health)      │
├───────────────────────────────────────────────────────────────────┤
│  dal/  (DATA-ACCESS LAYER — kept separate, the only boundary)      │
│   booking_repository.py · doctor_repository.py ·                    │
│   knowledge_repository.py · chunk_repository.py ·                   │
│   ingestion_job_repository.py (Postgres) · qdrant_client.py ·        │
│   — inherits core/, holds all SQL/filters, NO business logic       │
├───────────────────────────────────────────────────────────────────┤
│  common/  (config · observability · resilience · gemini_client)     │
└───────────────────────────────────────────────────────────────────┘
```

| Layer | Responsibility |
|-------|-------------|
| **app** | Composition root: initializes the ADK runtime, registers agents + tools, mounts the webhook (web chat channel) + API router for `modules/`; middleware & lifespan. `app/webhook/handler.py` calls `ai-agents/core/domain/emergency_rules.py` **the moment a message arrives, before entering the ADK runtime** — a red-flag match transfers straight to the `Emergency Agent`, skipping the Orchestrator entirely (Layer 1 safety, ADR-0019). Outside this branch, it contains no business logic. |
| **ai-agents/orchestrator** | Orchestrator Agent: observes the conversation, classifies customer intent, **transfers down** to the appropriate child agent (faq / symptom / booking / emergency) via session transfer. Still retains the ability to detect indirectly-phrased emergency signals itself (Layer 2 safety, a fallback for cases Layer 1 doesn't catch — ADR-0019). Never calls `dal/` directly. |
| **ai-agents/faq** | Answers policy / insurance / regulation / clinic operational questions. Tool `search_knowledge_base(query, category="policy"|"clinic_info")` → grounding, citation, "not found" if below threshold. |
| **ai-agents/symptom** | Suggests a specialty/doctor based on symptoms, per the intake process in [BIZ-001](../01-requirements/02-biz-patient-intake.md). First applies hard rules by patient category (`ai-agents/core/domain/intake_rules.py` — age, pregnancy, referral letter, named-doctor request, package checkups, vaccination); if none match, checks against the **triage table embedded in the system prompt** (not via Qdrant, ADR-0018), asks at most 3 questions, defaults to `General Internal Medicine` when unclear. **The doctor list (with profile: bio, clinical strengths) is rendered from the `doctors` table into context at session start** — the agent sees 100% of the list and picks `doctor_id` directly, no semantic search (ADR-0020). Tool `search_knowledge_base(query, category="medical_guide")` is only for open medical guidance (e.g., test preparation) — not used for specialty routing. Doesn't diagnose — only directs. |
| **ai-agents/booking** | Books/reschedules/cancels appointments through conversation. Tools call `dal/booking_repository.check_available_slots / create_booking / update_booking / cancel_booking` (cross-referencing `dal/doctor_repository` for the doctor's working schedule) — never writes its own SQL, never handles the race condition itself (that already lives in the `dal/` constraint). |
| **ai-agents/emergency** | Emergency Agent: gives a **static, fixed** response upon receiving a session transfer from the Orchestrator — directs the customer to the nearest medical facility or a hotline. Has no `tools.py`, calls no `dal/`, integrates with no external system. |
| **ai-agents/core** | `BaseAgent` (lifecycle, session-transfer contract), `BaseTool`, a versioned prompt loader, AI-specific exceptions (`SlotTakenError`, `LowConfidenceError`). |
| **modules/booking** | CRUD for the internal admin screen — staff edit/cancel bookings directly, without going through an agent/conversation. Calls the **same** `dal/booking_repository` as `ai-agents/booking`, but through a different entry point (plain REST CRUD, no LLM). Sharing a name with `ai-agents/booking` is acceptable — the two trees are completely separate, distinguished by path. |
| **modules/doctor** | CRUD for doctor management via an internal UI — fully replacing Sheets. Manages **all** doctor information in one `doctors` table: operational data (doctor code, specialty, phone, working days, room, shift) **and** descriptive profile (bio, education, clinical strengths — ADR-0020). Calls `dal/doctor_repository` (Postgres). |
| **modules/knowledge** | CRUD for knowledge content (`policy`/`clinic_info`/`medical_guide`) via an internal UI — fully replacing Sheets/markdown files. When staff hit "Publish," it just does `INSERT ingestion_jobs(status='pending_chunk')` and returns immediately — it does **not** run chunk/embed itself (§5.5, §6.4, ADR-0017, ADR-0021). |
| **modules/knowledge_ingestion** | An internal pipeline — **has no `controller.py`** (not exposed over HTTP): `chunk_service.py` (SemanticChunker + size guard) + `embedding_service.py` (batch embed + upsert), each phase with its own worker following the `run(job_id)` contract (`job_chunk.py`, `job_embedding.py`), triggered by `cron.py` (APScheduler polls `ingestion_jobs`, sweeps stuck jobs, auto-retries failed jobs) — **reused as-is from `rag-health`**, only table/field/category names changed (§5.5, ADR-0021). |
| **core** | `base_model.py`, `base_repository.py` (generic CRUD `BaseRepository[T]`), `base_service.py`, `base_response.py` (`StandardResponse[T]`/`PaginatedResponse[T]`), `exceptions.py` (the `AppException` hierarchy) — **reused as-is from `rag-health`**, shared by `modules/*` and `dal/*`. Placed at the root, not inside `modules/` (ADR-0021). Completely separate from `ai-agents/core` (base classes for agents/tools, not CRUD). |
| **dal** | `booking_repository.py`, `doctor_repository.py`, `knowledge_repository.py`, `chunk_repository.py`, `ingestion_job_repository.py` (SQLAlchemy + Postgres, inheriting `core/base_repository.py`; `bookings` has a partial unique index `WHERE status != 'cancelled'`/`SKIP LOCKED`), `qdrant_client.py` (search + upsert + payload filter by `category`). This is the **only place** with repositories that know real table/collection names (ADR-0013, ADR-0021). |
| **common** | Config (Pydantic Settings), `gemini_client.py` (LLM + embedding), structlog + tracing, retry/timeout — cross-cutting infrastructure, not business data. |

**Boundaries:**
- `ai-agents/` and `modules/` **never import each other**, and **never open a connection** to Postgres/Qdrant directly — both only call through `dal/`.
- `dal/` **contains no business logic** (it doesn't know "what double-booking means," only "raise an exception when the partial unique constraint fails") — the logic that interprets that error lives in `ai-agents/core/exceptions.py` or `core/exceptions.py`.
- Within `ai-agents/`, the agents (`orchestrator`, `faq`, `symptom`, `booking`, `emergency`) **never import each other** — the Orchestrator is the only thing that transfers down to child agents.
- `core/` (generic base classes) is allowed to reference SQLAlchemy types/Session since it doesn't know specific table names; only `dal/` (concrete repositories, inheriting `core/`) may declare real tables/collections (ADR-0021 clarifies ADR-0013).

---

## 5. Key Flows

### 5.1 Booking (FR-03) — the most important write path

```
Customer  orchestrator   booking_agent       Postgres
  │"book 9am tomorrow"│    │                  │
  ├────────────────►│      │                  │
  │   ├─ classify: BOOKING►│                  │
  │   │  transfer ─────────►│                  │
  │   │                     ├─ check_available_slots() ─►│
  │   │                     │  (cross-references doctors + bookings, same Postgres)
  │   │                     │◄── slot open ───│
  │   │ "9:00 slot is open" │◄─────────────────┤
  │◄───────────────────────┤                  │
  │ "name Kim, 090xxx"│     │                  │
  ├─────────────────►│      ├─ create_booking()►│
  │   │                     │   partial UNIQUE(doctor,slot) WHERE status!='cancelled'
  │   │                     │◄── OK / fail ────│
  │ "booking confirmed"│◄───┤                  │
  │◄─────────────────┤      │                  │

  * check_available_slots and create_booking are 2 SEPARATE calls → a real race window exists.
  * The constraint is the final check: a second INSERT for the same slot fails on its own
    → SlotTakenError → the agent apologizes, proposes another time. The constraint is a
    **partial unique index** `UNIQUE(doctor_id, slot_time) WHERE status != 'cancelled'` —
    not a plain table-wide unique constraint (ADR-0009).
```

### 5.2 Policy / FAQ Q&A (FR-04 → FR-05)

```
Customer  faq_agent          Qdrant        Gemini
  │ "how much is an endoscopy?"│  │             │
  ├────────────────────►├─ search_knowledge_base(category="policy") ─►│
  │           │                │◄── top-K context (or empty)│
  │           │  [if empty/below threshold] → "no information found" │
  │           │                ├─ build_prompt(context) ─────►│
  │           │                │  ◄── answer + grounding ─────│
  │           │  answer + citation │             │
  │◄────────────────────┤        │             │
```

### 5.3 Reschedule / Cancel (FR-03, Update/Cancel)

```
Customer → booking_agent → update_booking(booking_id, new_slot)
                              │
                              ├─ UPDATE bookings SET slot_time=? WHERE id=?
                              │   (new_slot collides with the partial UNIQUE (status != 'cancelled')
                              │    → SlotTakenError, keeps the old slot)
                              └─ responds to the customer with the result

Customer → booking_agent → cancel_booking(booking_id)
                              │
                              ├─ UPDATE bookings SET status='cancelled' WHERE id=?
                              │   (slot is freed immediately, no waiting-list/priority-notify mechanism)
                              └─ responds to the customer with the result
```

### 5.4 Emergency (FR-07) — two-layer defense (ADR-0019)

```
Customer sends a message
        │
        ▼
app/webhook/handler.py
        │
        ├─ Layer 1: emergency_rules.is_emergency(text)   (rule code, NO LLM call)
        │     │
        │     ├─ MATCH ──► session transfer → emergency_agent (skips the orchestrator entirely)
        │     │              (no tool call, no dal/ call)
        │     │              static response: "go to the nearest facility / call the hotline"
        │     │
        │     └─ NO MATCH ──► enters the normal ADK runtime
        │                              │
        │                              ▼
        │                     orchestrator classifies intent
        │                              │
        │                     Layer 2: the orchestrator (LLM) can still
        │                     detect indirectly-phrased emergency signals
        │                              │
        │                     MATCH ──► session transfer → emergency_agent (as above)
        ▼
  (no match at either layer → continues to the normal FAQ/Symptom/Booking flow)
```

Principle: Layer 1 handles the common case fast and reliably for red-flag keyword matches (BIZ-001 §3) — no LLM round-trip. Layer 2 is a safety net for phrasings the rule code didn't anticipate. Better an unnecessary emergency transfer than a missed one.

### 5.5 Knowledge Ingestion into RAG — a 2-phase, cron-polled pipeline, reused as-is from `rag-health` (ADR-0021)

```
Staff → modules/knowledge (CRUD UI)
                │
                ├─ create/edit a row in Postgres `knowledge_base`
                │    (category, title, content, status='draft')
                │
                └─ click "Publish" ──► modules/knowledge.services.publish(id)
                                          │
                                          ├─ INSERT ingestion_jobs(knowledge_id, status='pending_chunk')
                                          └─ returns immediately {job_id, status: pending} — does NOT run chunk/embed itself

Cron/APScheduler   modules/knowledge_ingestion            Qdrant   Postgres
      │                       │                              │         │
      ├─ poll ingestion_jobs ►│                              │         │
      │  (pending_chunk)      │                              │         │
      │                       ├─ job_chunk.run(job_id) ─────►│         │
      │                       │    chunk_service: SemanticChunker (percentile 80)
      │                       │    + MAX guard (split >1000 tokens, overlap 150)
      │                       │    + MIN guard (merge <100 tokens into the previous chunk)
      │                       │    → INSERT knowledge_chunks (pending_embed) ─────►│
      │                       ├─ UPDATE ingestion_jobs SET status='pending_embed' ►│
      │                       │                              │         │
      ├─ poll ingestion_jobs ►│                              │         │
      │  (pending_embed)      │                              │         │
      │                       ├─ job_embedding.run(job_id) ─►│         │
      │                       │    embedding_service: batches (EMBEDDING_BATCH_SIZE=100)
      │                       │    → gemini_client.embed_batch(chunks)      (Cloud)
      │                       │    → qdrant_client.upsert(batch, payload=
      │                       │        {knowledge_id, chunk_id, category, title, text}) ►│
      │                       │    → UPDATE knowledge_chunks SET status='embedded' ─────►│
      │                       ├─ UPDATE ingestion_jobs SET status='done' ───────────────►│
      │                       └─ UPDATE knowledge_base SET status='published',
      │                                  last_indexed_at=now() ─────────────────────────►│

Agent (faq/symptom) → search_knowledge_base(query, category) → Qdrant  (unchanged from §5.2)
```

* `job_chunk.run(job_id)`/`job_embedding.run(job_id)` follow the **exact same contract** as `rag-health` (claim a job with `UPDATE ... SET status=... WHERE status=... SKIP LOCKED`, idempotent — re-running doesn't create duplicate chunks/vectors).
* **Trigger kept identical to rag-health:** `cron.py` (APScheduler, reused as-is) polls `ingestion_jobs` on a cycle, invokes the matching worker; the job store lives in Postgres (`apscheduler_jobs`). The cron also sweeps stuck jobs (>30 min) and auto-retries `failed` jobs (10-minute cycle) — identical to rag-health's ADR-0009.
* **Manual trigger available (an added requirement):** `scripts/run_ingestion_job.py` calls **the exact same** two `run(job_id)` functions above to trigger immediately without waiting for the poll cycle — used when staff want to see a publish take effect right away, when retrying a `failed` job, or for a full backfill/re-index (replacing the old `scripts/ingest_knowledge.py`). There is no separate code path for "automatic" vs. "manual" (ADR-0021).
* Deleting/archiving a knowledge item → deletes its `knowledge_chunks` + calls `qdrant_client.delete_by_knowledge_id()`, avoiding "orphaned vectors."

This is still the **standard RAG flow** settled in [ADR-0017](#decision-log) (a system-managed content store → chunk → embed → vector store, no files/Sheets involved); the specific chunk/embed algorithm, module structure, and **cron-poll trigger mechanism** are reused as-is from `rag-health` in [ADR-0021](#decision-log) — the trade-off: Publish no longer takes effect instantly, with up to one poll-cycle of delay unless triggered manually.

---

## 6. Data Model

Core principle: **choose the datastore by query characteristics**, not force one store for every kind of data (ADR-0002, ADR-0016). After dropping Google Sheets, the system has **two** stores left: PostgreSQL (all structured data — transactions, configuration, raw knowledge content) and Qdrant (vectors for semantic search). This is still polyglot persistence by query characteristics (relational/CRUD vs. semantic search), just without Sheets as a third source.

### 6.1 PostgreSQL — transactional data, configuration, and raw knowledge content

| Table | Key columns | Role |
|------|-----------|---------|
| `bookings` | `id`, `patient_name`, `phone`, `doctor_id`, `slot_time`, `status`, `created_at` | The source of truth for every book/reschedule/cancel transaction. The **partial unique index** `UNIQUE(doctor_id, slot_time) WHERE status != 'cancelled'` guarantees no two *active* bookings collide on a slot — correct *every time*, independent of application logic. A partial index (not a plain table-wide `UNIQUE`) is used because cancelling only updates `status='cancelled'`, it doesn't delete the row — with a plain `UNIQUE`, a just-cancelled slot could never be rebooked (a new INSERT would collide with the cancelled row and fail wrongly, with no separate waiting list to compensate). |
| `doctors` | `id`, `full_name`, `title` (e.g., specialist grades), `specialty`, `phone`, `work_days` (e.g. array `[Mon,Wed,Fri]`), `room`, `shift`, `fee`, `is_active` **+ profile merged directly into the table:** `bio`, `education`, `photo_url`, `extra` (JSONB — for attributes added later, no migration needed) | **All doctor information in one table** — both operational data (looked up by `WHERE doctor_id = ?`, slot calculation) and descriptive profile (rendered into the `Symptom Agent`'s context, ADR-0020). At a scale of a few dozen doctors, a separate profile table or pushing this through Qdrant would be over-engineering. Staff edit it via `modules/doctor`. Fully replaces the `Doctors` tab in Sheets (ADR-0016). |
| `knowledge_base` | `id`, `category` (`policy`/`clinic_info`/`medical_guide`), `title`, `content` (text/markdown authored by staff), `status` (`draft`/`published`), `updated_at`, `last_indexed_at` | **The single source for authoring knowledge** — staff edit it via `modules/knowledge`. When `status='published'`, the content is chunked (→ `knowledge_chunks`) + embedded + upserted into Qdrant via `ingestion_jobs` (§5.5, §6.4, ADR-0021). This table is the document-level *system of record* (equivalent to `documents` in rag-health); Qdrant + `knowledge_chunks` are just a **derived copy** for search — if lost, they can be 100% re-indexed from here. There's no more `doctor_profile` category — doctor profiles have been merged into the `doctors` table (ADR-0020). |
| `knowledge_chunks` | `id`, `knowledge_id` (FK), `ordinal`, `text`, `vector_id`, `embed_status` (`pending_embed`/`embedded`) | **New (ADR-0021)** — the chunking output of `chunk_service` (SemanticChunker + size guard). `vector_id` points to the corresponding point in Qdrant. Kept separate from `knowledge_base` because a long document produces many chunks — they can't fit into a single `content` column. |
| `ingestion_jobs` | `id`, `knowledge_id` (FK), `status`, `error_msg`, `created_at`, `updated_at` | **New (ADR-0021)** — tracks pipeline progress for each Publish: `pending_chunk → chunking → pending_embed → embedding → done \| failed`. The cron polls this table to know which jobs need processing; allows retry (`scripts/run_ingestion_job.py --retry-failed`) without re-publishing from scratch. |
| `apscheduler_jobs` *(created/managed by APScheduler itself)* | — | **New (ADR-0021)** — APScheduler's job store (poll schedule, sweep, retry), reusing rag-health's mechanism as-is. Never queried directly from `dal/`/`modules/`. |
| `chat_session_links` *(optional, created if admin lookup is needed)* | `booking_id`, `session_id`, `user_id`, `created_at` | A thin mapping table — **stores no message content**. Just lets `modules/booking` quickly look up "the chat history for the customer who booked X": fetches `session_id` from here, then calls `SessionService.get_session()` for the real content. Doesn't replace ADK's `events` table. |

> The correctness of the transactional layer rests on the **partial unique index** `UNIQUE(doctor_id, slot_time) WHERE status != 'cancelled'` at the DB level, not on application-side checks (ADR-0009). All 7 tables above live in **the same Postgres instance** — Google Sheets is no longer a parallel configuration source (ADR-0016).

**Chat sessions — no separate message table:** Conversation history (customer messages, agent replies, tool calls) is managed by ADK's **`DatabaseSessionService`**, pointed at **this same Postgres instance**. On startup, ADK auto-creates 5 internal tables: `sessions`, `events` (a complete sequential log of every message/tool call), `app_states` (app-wide shared state), `user_states` (per-user state), `adk_internal_metadata`. This is ADK's internal schema and may change between versions — `dal/` or `modules/` must **never** write SQL/joins directly against the `adk_*` tables; all access to conversation history must go through the `SessionService` API (`get_session`, `append_event`, etc.), never reading the raw tables ([ADR-0015](#decision-log)).

### 6.2 Qdrant — static knowledge (categorized RAG) — a derived copy for search, the real source is `knowledge_base`

Vector collection: `vector(embedding)` + payload `{ knowledge_id, chunk_id, category, title, text }`. Embeddings are generated by the Gemini embedding API (same ecosystem as ADK/Gemini, ADR-0006), batched by `embedding_service` (ADR-0021). `knowledge_id`/`chunk_id` point back to `knowledge_base.id`/`knowledge_chunks.id` in Postgres — every vector can be traced back to its original authored source.

The **`category`** field allows filtering by knowledge type right at the query layer (`search_knowledge_base(query, category=...)` → a Qdrant payload filter), avoiding mixed context across domains during search:

| `category` | Content | Used by |
|-----------|----------|-----------|
| `policy` | Policy, insurance, regulations, price list | faq_agent |
| `clinic_info` | Opening/closing hours, holidays, promotions, amenities (parking, etc.) — authored via `modules/knowledge` | faq_agent |
| `medical_guide` | Open medical guidance (e.g., test/scan preparation — Use Case 6). **Does not contain** the symptom-to-specialty triage table (embedded in the system prompt, ADR-0018) and **does not contain** doctor profiles (in the `doctors` table, rendered into context — ADR-0020) | symptom_agent |

The payload is enough to build a citation straight from the search result; Qdrant supports native payload filtering, so filtering by `category` doesn't need a separate collection. **There's no separate knowledge cache layer** (e.g., per-session cache) — every knowledge query goes straight to Qdrant to guarantee a single source of truth; if `knowledge_base.content` changes but hasn't been re-published, Qdrant deliberately keeps the old version (a draft that hasn't been published never leaks out).

### 6.3 Where does doctor information live? — one `doctors` table, embedded into context (ADR-0020)

Doctor information now has only **two layers**, both in Postgres:

1. **The full doctor profile (Postgres `doctors`):** both operational data (doctor code, full name, specialty, phone, working days, room, shift, fee) **and** descriptive profile (bio, education, clinical strengths — the `bio`/`education`/`extra` columns). Staff edit all of it in one `modules/doctor` screen. This table is the **single source of truth** about doctors.

2. **Slot transaction data (PostgreSQL `bookings`):** which slots for which doctors are already booked. Combined with the schedule in (1), `check_available_slots()` computes the open slots — *working days come from `doctors`, booked slots come from `bookings`, both tables in the same DB, joined together*.

**How the agent "knows" about doctors — embedded in context, not semantic search:** at session start (or on a cache invalidation when `modules/doctor` edits data), the system queries the `doctors` table, renders the full list (with `doctor_id`, specialty, a bio summary, working days) into a JSON/Markdown block and places it into the `Symptom Agent`'s context. A question like "which doctor is good with gastroscopies?" is answered by the **LLM reading the entire list directly**, instead of a vector search. The `doctor_id` in the context block is the bridge back to the DB — the agent uses that exact id when calling the `check_available_slots(doctor_id)` / `create_booking(doctor_id, ...)` tools.

**Why merge into one table and drop semantic search for doctor profiles** (reversing an earlier decision to split `doctor_profile` out through Qdrant):

- **The data is too small relative to the context window:** a clinic averages 5–15 doctors, even a large chain tops out around ~50; the full list with profiles is only ~1,000–5,000 tokens. Vector DBs (RAG) exist to solve "data that doesn't fit in context" — that's not the problem here.
- **Embedding everything gives better retrieval quality:** listing/comparison questions ("do you have any pediatricians?", "which doctors work Saturdays?") are easy to miss with top-K vector search alone; with the LLM seeing 100% of the list, there's no retrieval-miss risk.
- **Less infrastructure, fewer failure points:** no separate chunk → embed → upsert pipeline needed for doctors, no risk of Qdrant drifting from Postgres when staff edit a profile. A fix in `modules/doctor` takes effect on the very next render.
- **One admin screen:** staff edit doctor info (both shift schedule and bio) in one place, instead of remembering "shifts get edited in doctor, bio gets edited in knowledge."

**Trade-off & the threshold to revisit:** if the system grows into a multi-tenant platform with hundreds of clinics / thousands of doctors on one shared agent, or profiles balloon into long documents, the context block will exceed a reasonable size — that's the point to split profiles back out into `knowledge_base` + Qdrant as in the earlier design (ADR-0020 states this threshold explicitly).

`symptom_agent` flow: reads the **doctor list embedded in context** to pick the right doctor by symptom/description, then `booking_agent` uses `bookings` (Postgres) to **confirm the slot is open and finalize the booking** via `doctor_id`.

### 6.4 Lifecycle of a knowledge item: from authoring to the agent answering

```
draft (knowledge_base) → Publish → ingestion_jobs(pending_chunk)
      → job_chunk (→ knowledge_chunks, pending_embed) → ingestion_jobs(pending_embed)
      → job_embedding (→ Qdrant, knowledge_chunks.status=embedded) → ingestion_jobs(done)
      → knowledge_base.status=published → agent search_knowledge_base()
```

- **Editing already-published content:** staff edit `content`, and `status` implicitly reverts to "not yet synced" until Publish is clicked again (creating a new `ingestion_jobs` row) — preventing Qdrant from ever automatically exposing half-finished draft content.
- **A job fails midway:** `ingestion_jobs.status='failed'` leaves `knowledge_base.status='draft'` — staff can see the publish didn't finish; retry via `scripts/run_ingestion_job.py --retry-failed` (ADR-0021) without re-authoring the content.
- **Deleting a knowledge item:** deleting (or archiving) the `knowledge_base` row cascades to delete its `knowledge_chunks`, and the service calls `qdrant_client.delete_by_knowledge_id()` to clean up the corresponding vectors — no "orphaned vectors" left behind.
- **No intermediate step outside the system** (no files, no Sheets) — true to the "standard RAG flow" spirit: one content store → chunk → embed → vector store (ADR-0017), with the specific pipeline reused from `rag-health` (ADR-0021).

---

## 7. AI-specific Design

| Aspect | Decision |
|-----------|-----------|
| **AI engine** | Google ADK — always the latest stable version, never pinned to a specific version in the design. The LLM (Gemini) is chosen **flexibly based on cost/effectiveness at deployment time** (Flash/Pro/other) via an env var, not fixed in the architecture. Embeddings use the Gemini embedding API in the same ecosystem ([ADR-0006](#decision-log)). |
| **Multi-agent routing** | The `Orchestrator Agent` classifies intent (including emergency detection), transfers sessions. Each agent has a narrow tool scope → less room for confusion ([ADR-0001](#decision-log)). |
| **Emergency handling** | **Two layers of defense** (BIZ-001 §3, ADR-0019): Layer 1 — `emergency_rules.py` (rule code, running in `app/webhook/handler.py` before entering the ADK runtime, checking against the red-flag list in BIZ-001 §3, no LLM call); Layer 2 — the `Orchestrator Agent` (LLM) still detects indirectly-phrased emergency signals while classifying intent, as a safety net. Both layers transfer to the `Emergency Agent` → a static response (directing to the nearest medical facility / a hotline). No tool calls, no integration with an external medical dispatch system — out of scope for this system ([ADR-0014](#decision-log)). |
| **Symptom-to-specialty triage** | Hard rules by patient category (age, pregnancy, referral letter...) live in `ai-agents/core/domain/intake_rules.py` (plain Python, testable, per BIZ-001 §4); the symptom-to-specialty table (BIZ-001 §6–7) is **embedded directly in the system prompt** of the `Symptom Agent`, bypassing Qdrant — because this is hard-enum logic that must be exactly correct, not open knowledge ([ADR-0018](#decision-log)). |
| **Doctor profiles** | Merged entirely into the `doctors` table (Postgres), **the full list rendered into context** for the `Symptom Agent` at session start — bypassing Qdrant. A few dozen records fit comfortably in context; the LLM sees 100% of the list, so there's no retrieval-miss risk on listing/comparison questions; the `doctor_id` in context is the bridge when calling booking tools (§6.3, [ADR-0020](#decision-log)). |
| **RAG grounding** | FAQ/Symptom are constrained to "answer only from context"; below the similarity threshold → "no information found," no free-form LLM generation ([ADR-0008](#decision-log)). |
| **Unified knowledge** | All static knowledge (`policy`, `clinic_info`, `medical_guide`) is queried through a single Qdrant; no separate context cache for knowledge, avoiding two sources drifting apart ([ADR-0002](#decision-log)). Doctor profiles are a deliberate exception — living in the `doctors` table, embedded in context (ADR-0020). |
| **Knowledge categorization** | Qdrant payload filter by `category` → each agent only searches within its own knowledge type, no mixed context ([ADR-0007](#decision-log)). |
| **Booking correctness** | LLM output is never trusted for write operations. Correctness rests on a Postgres constraint; the agent only relays the result ([ADR-0009](#decision-log)). |
| **Resilience** | Retry + timeout wraps every Gemini/Qdrant/Postgres call (`common/resilience.py`). |
| **Knowledge ingestion (RAG)** | Standardized through the `knowledge_base` table (Postgres) — no markdown files or Sheets. Staff author/edit via `modules/knowledge`; clicking "Publish" only creates an `ingestion_jobs` row, and a 2-phase pipeline in `modules/knowledge_ingestion` runs in the background via **cron-poll** (§5.5). The pipeline + trigger (chunking, batch embedding, job worker, cron) are **reused as-is from `rag-health`** ([ADR-0021](#decision-log)); the macro-decision carries over from ([ADR-0017](#decision-log)). |
| **Chunking strategy** | `chunk_service.py`: `SemanticChunker` (percentile 80) preserves semantic flow + a MAX guard (splits chunks >1000 tokens, 150-token overlap) + a MIN guard (merges chunks <100 tokens into the previous one) — avoiding chunks too large for the embedding token limit (~2048 tokens/call) or too small to carry context. Reused as-is from `rag-health` (ADR-0021). |
| **Batch embedding** | Chunks are grouped into batches (`EMBEDDING_BATCH_SIZE`, default 100) → `embed_batch()` is called once per batch → a batch-upsert into Qdrant, reducing round-trips. Triggered via cron-poll (`cron.py`, APScheduler), or **manually** via `scripts/run_ingestion_job.py` (triggers immediately without waiting for the poll, retries a failed job, backfill, full re-index) — both share the same `job_chunk.run()`/`job_embedding.run()`, with no separate logic for "manual" (ADR-0021). |
| **Chat session management** | ADK's `DatabaseSessionService` points at the existing Postgres — no separate `messages`/`chat_history` table is built; ADK auto-creates & manages `sessions`/`events`/`app_states`/`user_states`. Long-term memory (an agent recognizing a returning customer across widely-spaced visits) is left open, using `MemoryService` (`VertexAiMemoryBankService`/`VertexAiRagMemoryService`) if a real need arises — **not implemented** in the current scope ([ADR-0015](#decision-log)). |
| **AI observability** | Trace spans for every step (intent → agent → tool → result); logs similarity score, slot conflicts, token usage. |
| **Domain isolation** | Pure business rules in `ai-agents/core/domain/` (slot validation, phone formatting, grounding) import no SDK — pure unit-testable. |
| **AI quality gate** | `eval/` measures separately from unit tests: retrieval (Hit Rate@k, MRR), intent routing accuracy, faithfulness (LLM-judge), booking concurrency. The real gate lives in `tests/eval/test_eval_gate.py` — exits 1 on FAIL (§8, §11). |

---

## 8. Project Layout

```
ai-clinic-agent/
├── app/                          # Composition root (FastAPI + ADK)
│   ├── main.py                   # creates the app, mounts the router, lifespan
│   ├── runtime.py                # registers agents + tools
│   ├── webhook/
│   │   └── handler.py            # calls emergency_rules first, then hands off to the orchestrator
│   └── api/v1/router.py          # mounts modules/'s CRUD API
│
├── ai-agents/                    # AI layer
│   ├── core/                     # base classes for agents
│   │   ├── base_agent.py
│   │   ├── base_tool.py
│   │   ├── prompt_loader.py
│   │   ├── exceptions.py         # SlotTakenError, LowConfidenceError
│   │   └── domain/                # pure Python business rules
│   │       ├── booking_rules.py
│   │       ├── intake_rules.py    # hard rules by patient category (BIZ-001 §4)
│   │       ├── emergency_rules.py # red-flag emergency screening, Layer 1 (BIZ-001 §3, ADR-0019)
│   │       └── grounding.py
│   │
│   ├── orchestrator/             # classifies intent, transfers to child agents
│   │   ├── agent.py
│   │   └── prompt.py
│   │
│   ├── faq/
│   │   ├── agent.py
│   │   ├── tools.py
│   │   └── prompt.py
│   │
│   ├── symptom/
│   │   ├── agent.py
│   │   ├── tools.py
│   │   └── prompt.py             # holds the BIZ-001 §6-7 triage table embedded directly
│   │
│   ├── booking/
│   │   ├── agent.py
│   │   ├── tools.py
│   │   └── prompt.py
│   │
│   └── emergency/                 # static response, no tools.py
│       ├── agent.py
│       └── prompt.py
│
├── modules/                       # Business layer (no AI)
│   ├── booking/                   # booking CRUD, bypasses agents
│   │   ├── controller.py
│   │   └── services.py
│   │
│   ├── doctor/                    # doctor CRUD + profile (replaces Sheets, ADR-0020)
│   │   ├── controller.py
│   │   └── services.py
│   │
│   ├── knowledge/                 # knowledge CRUD + publish trigger
│   │   ├── controller.py
│   │   └── services.py           # publish() = INSERT ingestion_jobs → calls knowledge_ingestion
│   │
│   └── knowledge_ingestion/       # internal pipeline — no controller.py (ADR-0021, reused from rag-health)
│       ├── chunk_service.py       # SemanticChunker percentile-80 + MAX guard(>1000,overlap150)
│       │                          #   + MIN guard(<100, merges into the previous chunk)
│       ├── embedding_service.py   # batches (EMBEDDING_BATCH_SIZE=100) → embed_batch → qdrant upsert
│       ├── job_chunk.py           # Worker — contract: run(job_id: UUID), SKIP LOCKED, idempotent
│       ├── job_embedding.py       # Worker — contract: run(job_id: UUID), SKIP LOCKED, idempotent
│       └── cron.py                # Trigger (ADR-0021): APScheduler polls ingestion_jobs
│                                  #   → job_chunk.run(job_id) / job_embedding.run(job_id)
│                                  #   • sweeps pending >30 min, retries failed every 10 min
│                                  #   job store → Postgres (apscheduler_jobs table)
│
├── core/                           # Shared CRUD base classes — reused as-is from rag-health (ADR-0021)
│   ├── base_model.py              # id (UUID) + timestamps
│   ├── base_repository.py         # BaseRepository[T]: generic get/list/create/update/delete
│   ├── base_service.py            # logging hook, standard error handling
│   ├── base_response.py           # StandardResponse[T], PaginatedResponse[T]
│   └── exceptions.py              # AppException, NotFoundError, ValidationError...
│
├── dal/                           # Data-access layer — kept separate, inherits core/base_repository.py
│   ├── booking_repository.py     # partial unique index (WHERE status != 'cancelled'), SKIP LOCKED
│   ├── doctor_repository.py      # CRUD for the doctors table
│   ├── knowledge_repository.py   # CRUD for the knowledge_base table
│   ├── chunk_repository.py       # CRUD for the knowledge_chunks table (ADR-0021)
│   ├── ingestion_job_repository.py # get_pending (SKIP LOCKED), get_by_knowledge, get_failed (ADR-0021)
│   ├── qdrant_client.py          # search + upsert + delete_by_knowledge_id
│   └── session.py                # initializes the ADK DatabaseSessionService pointed at Postgres
│
├── common/                        # Cross-cutting infrastructure
│   ├── config.py
│   ├── gemini_client.py
│   ├── observability.py
│   └── resilience.py
│
├── eval/                           # AI quality measurement
│   ├── golden_set_rag.yaml
│   ├── golden_set_intent.yaml
│   ├── golden_set_booking.yaml
│   ├── metrics.py                 # the single source for every measurement formula
│   └── runner.py                  # emits REPORT.md; exits 1 on FAIL
│
├── alembic/
│   ├── env.py
│   └── versions/
│
├── scripts/
│   └── run_ingestion_job.py      # calls job_chunk.run()/job_embedding.run() directly (ADR-0021):
│                                  #   --knowledge-id <id> · --retry-failed · --reindex-all
│                                  #   (replaces the old scripts/ingest_knowledge.py)
│
├── tests/
│   ├── unit/
│   │   ├── ai_agents/
│   │   │   ├── test_booking_rules.py
│   │   │   ├── test_grounding.py
│   │   │   └── test_intent_routing.py
│   │   └── modules/
│   │       ├── test_booking_service.py
│   │       └── knowledge_ingestion/
│   │           ├── test_chunk_service.py     # chunking + size guard (ADR-0021)
│   │           └── test_embedding_service.py # batch embed + upsert (mocked)
│   ├── integration/
│   │   ├── test_booking_concurrency.py  # ⭐ prevents double-booking
│   │   ├── test_booking_flow.py
│   │   ├── test_faq_grounding.py
│   │   └── test_ingestion_pipeline.py   # publish → job_chunk → job_embedding → real Qdrant
│   └── eval/
│       ├── test_retrieval_metrics.py
│       ├── test_faithfulness.py        # @pytest.mark.llm, runs nightly
│       └── test_eval_gate.py           # @pytest.mark.eval — the real gate
│
├── docs/
│   ├── 01-architecture.md
│   └── ADR/                       # see the full index in §11
│
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── alembic.ini
├── pyproject.toml                              # deps, ruff, mypy, pytest
└── README.md
```

**Import conventions:**
- `ai-agents/` and `modules/` **never import each other**, and **never open a connection** to Postgres/Qdrant directly — both only call through `dal/`. If they need the same data (e.g., the `bookings` table), both call `dal/booking_repository.py` — never through each other.
- Within `ai-agents/`, the agents (`orchestrator`, `faq`, `symptom`, `booking`, `emergency`) **never import each other** — the Orchestrator is the only entry point that transfers down to child agents (session transfer).
- Concrete repositories (that know real table/collection names) **may only live in `dal/`** — this is the only boundary that touches storage infrastructure in the sense of "knowing the real schema." `ai-agents/*/tools.py` and `modules/*/services.py` call `dal/` through plain Python functions, never writing their own SQL/Qdrant filters. `core/base_repository.py` (generic, reused from rag-health) is the allowed exception: it doesn't know specific tables, it only provides generic CRUD functions for `dal/*_repository.py` to inherit (ADR-0021 clarifies ADR-0013).
- `ai-agents/core/domain/` is pure Python, testable offline; it's the only place holding the AI layer's business rules. `modules/knowledge_ingestion/` (chunk_service, embedding_service) is also pure Python for the chunking algorithm itself, only calling out (Gemini/Qdrant) through `common/gemini_client` and `dal/qdrant_client`.
- **Metrics rule:** `eval/metrics.py` is the single source for every measurement formula. Tests in `tests/eval/` only verify the formulas are correct using fake input — they never assert a real quality threshold. The one real quality gate lives in `tests/eval/test_eval_gate.py` (`@pytest.mark.eval`) and `eval/runner.py` (exits 1 on FAIL).

---

## 9. Deployment View

`docker-compose` has 3 services: **app** (FastAPI + ADK + APScheduler running in-process, stateless), **qdrant** (vectors), **postgres** (transactional `bookings`, configuration `doctors`, raw knowledge `knowledge_base` + `knowledge_chunks`/`ingestion_jobs`/`apscheduler_jobs` for the RAG pipeline **plus** the internal session/event data managed by ADK's `DatabaseSessionService` — all in the same database). The app can scale horizontally because it holds no local state — all durable data lives in Postgres/Qdrant, not in the app process's RAM; running multiple app instances at once **remains safe** even though every instance has its own cron polling `ingestion_jobs`, because workers claim jobs with `SKIP LOCKED` (only one instance wins each job, ADR-0021). Only **one** required external service remains: the Gemini API (no more Google Sheets, ADR-0016).

```
            ┌──────────┐      ┌──────────┐
Web chat ──►│  app(s)  │─────►│  Qdrant  │  (RAG vectors — a derived copy, real source in Postgres)
            │ FastAPI  │─────►│ Postgres │  (bookings, doctors, knowledge_base + chunks/jobs, sessions/events)
            │ + ADK    │      └──────────┘
            └────┬─────┘      ┌──────────────┐
                 └───────────►│  Gemini API  │  (LLM + embedding, model chosen flexibly)
                              └──────────────┘
```

> A self-hosted stack (Qdrant + Postgres via Docker) plus a single AI provider (Google/Gemini for both LLM and embeddings) — not locked into a specific cloud datastore, easy to run locally, easy to port elsewhere. With no more Google Sheets dependency, the entire business can run **completely offline from Google Workspace**, with only the Gemini API remaining as an AI dependency.

---

## 10. Traceability Map (Requirement → Module)

| Requirement | Responsible module |
|---------|-------------------------|
| FR-01 Webhook receives conversation | app/webhook → ai-agents/orchestrator |
| FR-02 Intent classification | ai-agents/orchestrator (prompt + transfer) |
| FR-03 Book / reschedule / cancel (via conversation) | ai-agents/booking (tools → Postgres, partial unique index `WHERE status != 'cancelled'`) |
| FR-04 Semantic Retrieval | ai-agents/faq, ai-agents/symptom (search_knowledge_base) |
| FR-05 Grounded Answer + citation | ai-agents/faq (core/domain/grounding.py + tools) |
| FR-06 Doctor suggestion by symptom | ai-agents/symptom (hard rules in `intake_rules.py` + the triage table in the prompt per [BIZ-001](../01-requirements/02-biz-patient-intake.md) + the doctor list with profiles rendered from `dal/doctor_repository` into context (ADR-0020) + Qdrant `medical_guide` for open medical guidance) |
| FR-07 Detect & respond to emergencies | Layer 1: `ai-agents/core/domain/emergency_rules.py` (rule code, called from `app/webhook/handler.py`); Layer 2: ai-agents/orchestrator (LLM, fallback) → both transfer to ai-agents/emergency (static response) |
| — Manual booking administration (admin, bypasses agents) | modules/booking (direct CRUD on Postgres) |
| — Doctor administration (operational + profile) | modules/doctor (CRUD on Postgres `doctors`, replaces Sheets; ADR-0020) |
| — Knowledge administration & ingestion (RAG) | modules/knowledge (CRUD on Postgres `knowledge_base` + publish trigger) → modules/knowledge_ingestion (chunk + batch embed + Qdrant, reused from rag-health, ADR-0021); scripts/run_ingestion_job.py for manual trigger/retry/backfill/re-index |
| — AI quality measurement (retrieval, intent, faithfulness, concurrency) | eval/ + tests/eval/test_eval_gate.py |

---

<a id="decision-log"></a>

## 11. Decision Log

| # | Decision | Status | Rationale |
|---|-----------|-----------|------------|
| **0001** | Multi-Agent within a single deployable (ADK) | Accepted | Clear intent boundaries, simple to operate; each agent can be split into an independent service later without rewriting logic. |
| **0002** | Polyglot persistence (2 stores): Postgres (transactions + configuration + raw knowledge content) + Qdrant (RAG, a derived search copy) | Accepted | Choose the store by query characteristics, not by "business data type." **Replaces an original all-in-Sheets design** because Sheets has no transactions/constraints → couldn't prevent double-booking; a ~100 req/100s rate limit and 300–800ms latency don't suit a transactional layer. Sheets was later dropped entirely (ADR-0016), consolidating configuration + raw knowledge into Postgres; Qdrant is now just a derived copy that can be re-indexed from Postgres at any time. |
| **0003** | No Port/Adapter abstraction per provider | Accepted | The stack is already fixed; an interface layer would add boilerplate out of proportion to scope. Keeping `dal/` separate (ADR-0013) already captures most of the same benefit without an abstract interface per provider. |
| **0004** | PostgreSQL for the bookings table | Accepted | ACID + a partial unique index prevents double-booking at the DB level (ADR-0009); `SKIP LOCKED` for sync jobs; self-hosted via Docker, not locked to a cloud datastore. |
| **0005** | Postgres as the source of truth; Sheets only a one-way read-only mirror | **Superseded by 0016** | Preserved the "view in Excel" experience for staff without allowing writes from two sources → avoiding conflicting data. (No longer applicable: Sheets has been fully removed, see ADR-0016.) |
| **0006** | Google ADK (always latest) + Gemini (LLM + embedding), model chosen flexibly | Accepted | ADK already supports multi-agent/session transfer; consolidating LLM and embeddings into one ecosystem reduces integration complexity; the specific model (Flash/Pro) is chosen flexibly by cost/effectiveness instead of being fixed in the architecture. |
| **0007** | Qdrant as the vector store, payload filter by `category` | Accepted | Native vector search + payload filtering (filtering by category needs no extra collections); HNSW; runs locally via Docker; matches the stack of other RAG projects → consistent operations. |
| **0008** | RAG grounding + a "not found" fallback | Accepted | FAQ/medical — a wrong answer has consequences; must be grounded in context, and below the similarity threshold it doesn't generate freely. |
| **0009** | Prevent double-booking with a DB constraint, not an application lock | Accepted | A constraint is correct *every time* in one place; an application-level lock has to be re-implemented everywhere and isn't guaranteed correct under every race. |
| **0010** | Fully self-hosted via docker-compose, not locked to a cloud | Accepted | Portable, easy to run locally for demos/portfolio; the backend is stateless and scales horizontally; avoids dependency on a proprietary cloud datastore. |
| **0011** | Physically separating `ai-agents/` (AI layer) from `modules/` (non-AI business layer) | Accepted | The two parts have different rates of change and risk: agents/prompts change with conversation-quality experiments (needs `eval/`), while admin CRUD is stable against ordinary business requirements. Merging them would make a prompt change trigger unrelated rebuilds/tests. |
| **0012** | `eval/` as its own quality gate, separate from unit tests | Accepted | AI quality (retrieval, intent routing, faithfulness) isn't a binary pass/fail like a unit test — it needs measured thresholds, a golden set, and reporting over time. Kept separate so it doesn't get mixed into the normal fast CI; the real gate only runs when needed (`pytest -m eval`). |
| **0013** | Splitting `dal/` into its own layer, independent of `ai-agents/` and `modules/` | Accepted | Both layers above need to read/write the same data (e.g., `bookings`) but shouldn't open their own connections or write their own SQL — swapping a datastore or adding a cache only requires editing `dal/`, not chasing down every tool/service. This is the only boundary containing concrete repositories (clarified by ADR-0021). |
| **0014** | Emergency Agent gives a static response, no automated medical dispatch | Accepted | Prioritizes safety and simple implementation: the AI system directs the customer to contact emergency services themselves (nearest facility/hotline) instead of automatically integrating with an alert/medical-staff dispatch system — avoiding the legal and technical risk of an AI deciding real medical actions. |
| **0015** | Using ADK's `DatabaseSessionService` on the existing Postgres, no separate chat message table | Accepted | ADK already fully manages conversation history (`sessions`/`events`) when pointed at a relational DB; building a parallel `messages`/`chat_history` table would duplicate that responsibility and risk drifting from the source ADK manages. |
| **0016** | Dropping Google Sheets, moving all configuration (`doctors`) + raw knowledge (`knowledge_base`) into Postgres | Accepted | A single administrative source (Postgres), avoiding two-way Sheets↔system sync and the risk of drifting data; the trade-off is having to build internal CRUD UIs (now `modules/doctor`, `modules/knowledge`) instead of leveraging familiar Excel operations. |
| **0017** | Standardizing RAG ingestion: `knowledge_base` (Postgres) → chunk → embed → Qdrant, triggered on "Publish" | Accepted (trigger refined by 0021: cron-poll instead of instant) | The correct standard RAG model: one system-managed content store (not an external file/Sheets) → embed → vector store — no PR merges or manual file steps involved. |
| **0018** | The symptom-to-specialty triage table (BIZ-001 §6-7) embedded directly in the system prompt, bypassing Qdrant RAG | Accepted | This is hard-enum logic that must be exactly correct (a list of 14 valid specialties), not open knowledge — RAG risks not matching 100% against colloquial phrasing; embedding it in the prompt guarantees the agent always has the full table, at the cost of needing a code change + deploy instead of a `modules/knowledge` UI edit when the business rule changes. |
| **0019** | Two-layer emergency screening: rule code (`emergency_rules.py`) runs before any LLM call, the Orchestrator (LLM) as a second safety net | Accepted | Life safety is the absolute top priority (BIZ-001 §3, §10) — rule code is fast, reliable, and model-independent for cases matching known red-flag keywords; the Orchestrator (LLM) still serves as a fallback for indirect phrasing the rule code misses. Better an unnecessary emergency transfer than a missed one. |
| **0020** | Merging doctor profiles into the `doctors` table, rendering the full list into the Symptom Agent's context — dropping the `doctor_profile` category from Qdrant | Accepted | A few dozen records (~1–5k tokens) fit comfortably in context — RAG is a tool for data that exceeds the context window, and using it here is over-engineering; the LLM sees 100% of the list, so there's no retrieval-miss risk on listing/comparison questions; this also removes the need for a separate embedding pipeline and the risk of Postgres↔Qdrant drift. Partially revises ADR-0007/0017 (dropping the `doctor_profile` category). |
| **0021** | Reusing `core/` (CRUD base classes), the RAG ingestion pipeline (chunk + batch embedding, job workers), **and the cron-poll trigger mechanism** as-is from the `rag-health` project, only renaming tables/fields/categories; dropping `modules/core` | Accepted | `knowledge_base` content can be long documents, needing real chunking + batch embedding (not the rough "split by heading" in ADR-0017) — an already-proven pipeline + cron sweep/retry was available, no need to redesign from scratch; publish no longer runs synchronously in the request, so there's no timeout risk for long documents. Workers follow the `run(job_id)` contract, decoupled from the trigger, so a manual run (`scripts/run_ingestion_job.py`) shares the same code as the cron. |
| **0022** | Renaming the `data/` directory (ADR-0013) to `dal/` | Accepted | "data" was too generic and easy to confuse; "dal" makes it explicit this is the Data Access Layer. A pure path rename, with no change to the boundaries/responsibilities already decided in ADR-0013; historical ADRs that say `data/` keep their original wording. |
