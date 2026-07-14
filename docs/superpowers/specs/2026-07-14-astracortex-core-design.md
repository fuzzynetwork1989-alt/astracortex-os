# AstraCortex Core — Design Spec (v1.0)

**Date:** 2026-07-14  
**Product:** AstraCortex — Cognitive Operating System  
**Scope:** Core Cognitive OS (web control plane + FastAPI runtime). XR clients deferred to v2.

## 1. Product identity

AstraCortex is not a chatbot. It is a **cognitive operating layer** that:

- holds goals across sessions,
- plans hierarchically,
- retrieves governed knowledge (RAG + multi-layer memory),
- executes typed tools under policy,
- reflects before writing long-term memory,
- and exposes full traces for trust and replay.

**Reasoning core:** SpaceXAI / xAI Grok (`grok-4.5` planner/critic, `grok-4.3` executor by default).

## 2. What makes v1 next-gen (first-of-kind *product shape*)

Novelty is integration of production primitives into one OS, not invented physics:

| Differentiator | Implementation in v1 |
|---|---|
| Cognitive graph | Tasks ↔ steps ↔ tool_calls ↔ memories ↔ reflections linked by IDs |
| Multi-layer governed memory | Working (Redis), episodic, semantic, reflective with write gates |
| Memory provenance | Every semantic item stores `source`, `confidence`, `evidence_ids` |
| Conflict arbitration | Semantic writes detect key conflicts; store contradiction records instead of blind overwrite |
| Plan versioning | Every plan revision stored in `plan_versions` with full JSON |
| Maker–checker loop | Planner / executor / critic as separate model roles |
| Policy-conditioned autonomy | `suggest` \| `act_with_approval` \| `full` per request |
| Evidence-linked answers | Citations from RAG chunks + memory IDs in final payload |
| Cost budgets | Per-task token/step budget tracking |
| Outcome-weighted memory | Importance score boosted on positive feedback |
| Trace replay | Full step/tool/reflection timeline via `/traces/{task_id}` |
| Session rehydration | Resume session with working + episodic context |
| Adaptive retrieval | Task-type-aware retrieval mix (RAG vs memory vs both) |
| Goal drift check | Critic flags when result diverges from original goal |
| Reflection-gated writes | Semantic memory only after critic `should_write_memory` |

## 3. Architecture

```
Next.js control plane  →  FastAPI gateway  →  Agent runtime
                              │
              ┌───────────────┼───────────────┐
              v               v               v
         PostgreSQL+pgvector  Redis      Object storage
         (state, memory, RAG) (working)  (uploads)
              │
              v
         SpaceXAI (xAI) LLM + embedding path
```

### Agent loop

```
Goal → load WM + retrieve (episodic/semantic/RAG)
  → planner creates versioned plan
  → for each step: policy → tool|LLM → observe → log
  → critic reflects (drift, quality, write decision)
  → curated memory writes → SSE done
```

## 4. Data model

See SQLAlchemy models in `backend/app/db/models.py`. Core tables:

- `users`, `organizations`, `org_members`
- `sessions`, `tasks`, `task_steps`, `plan_versions`
- `documents`, `chunks`, `embeddings`
- `episodic_memory`, `semantic_memory`, `reflections`
- `tool_calls`, `audit_events`, `approvals`, `feedback`

## 5. API surface

- Auth: register, login, logout, me  
- Sessions, tasks (create, get, cancel, approve)  
- Chat + SSE stream  
- Documents upload/ingest/list  
- Memory episodic/semantic/reflections  
- Traces, audit, feedback, health, cognitive-graph  

## 6. Stack

| Layer | Choice |
|---|---|
| UI | Next.js App Router |
| API | FastAPI + SSE |
| DB | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| LLM | xAI OpenAI-compatible API |
| Auth | JWT + bcrypt |
| Local run | Docker Compose |

## 7. Non-goals for v1.0

- Training QLoRA UI (hooks/config only)
- Quest 3 / RayNeo clients
- Enterprise SSO / billing
- Multi-region HA

## 8. Success criteria

1. `docker compose up` boots all services  
2. Register → login → chat with streamed plan/steps  
3. Upload doc → ingest → grounded answer with citations  
4. Task produces episodic + reflection rows  
5. Trace and cognitive-graph endpoints return linked history  

## 9. Roadmap

- **v1.0** — this Core  
- **v1.1** — expanded tools, dry-run, eval harness  
- **v1.2** — QLoRA training + adapter serving  
- **v1.3** — SSO, RBAC polish, quotas  
- **v2** — AstraCortex Spatial (Quest 3 + RayNeo)  
