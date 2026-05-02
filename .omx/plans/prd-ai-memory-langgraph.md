# AI memory improvement plan

## Requirements summary

The `water-info-ai` module needs production-grade memory aligned with LangGraph's current memory model:

- Short-term memory: thread/session-scoped state that can resume a conversation and graph execution.
- Long-term memory: user/application-scoped facts, preferences, decisions, and operational lessons that can be recalled across sessions.
- Existing behavior must remain compatible with the current REST/SSE APIs and conversation history endpoints.
- Use the existing PostgreSQL and pgvector stack first; add LangGraph Postgres persistence dependency only as an explicit implementation decision.

## Current repo facts

- The main graph is compiled without `checkpointer` or `store`, so LangGraph persistence is not active yet: `water-info-ai/app/graph.py:28` and `water-info-ai/app/graph.py:73`.
- API entrypoints manually hydrate the last 20 messages into `messages` before graph invocation: `water-info-ai/app/main.py:136`, `water-info-ai/app/main.py:333`, and `water-info-ai/app/main.py:401`.
- Conversation tables already exist for sessions, messages, snapshots, summaries, and memory items: `water-info-ai/app/database.py:201`, `water-info-ai/app/database.py:269`, and `water-info-ai/app/database.py:282`.
- Memory write methods are placeholders with no read/search/update path yet: `water-info-ai/app/database.py:455` and `water-info-ai/app/database.py:471`.
- The project already has embedding settings and pgvector-backed knowledge retrieval, which can be reused for semantic memory search: `water-info-ai/app/config.py:23`, `water-info-ai/app/database.py:817`, and `water-info-ai/app/rag/embedder.py:20`.

## LangGraph guidance applied

- LangGraph treats short-term memory as state persisted by a checkpointer keyed by thread ID.
- LangGraph treats long-term memory as JSON documents in a store, organized by namespace and key.
- Production Postgres checkpointers/stores require setup/migrations before use.
- Long-term memory should choose a write strategy: hot-path writes for immediately useful facts, background writes for lower latency and cleaner separation.

Primary references:

- https://docs.langchain.com/oss/python/langgraph/add-memory
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/concepts/memory

## Recommended architecture

Use three memory layers, because this project has both chat UX and flood-response business state:

1. Conversation memory
   - Scope: `session_id`.
   - Source: `conversation_message`, `conversation_summary`, optional LangGraph checkpoint.
   - Use: restore recent dialogue and compact older turns.

2. Business working memory
   - Scope: `session_id`.
   - Source: `conversation_snapshot` plus selected graph state fields.
   - Use: resume risk level, plan context, agent progress, and generated artifacts.

3. Long-term semantic memory
   - Scope: namespace tuple such as `(user_id, "flood_assistant")`, `(org_id, "flood_ops")`, or `("global", "flood_ops")`.
   - Source: upgraded `memory_item` table with metadata, optional embedding, dedupe hash, lifecycle fields.
   - Use: recall user preferences, station-specific lessons, prior decisions, recurring risk patterns, and operator feedback across sessions.

## Implementation steps

1. Define memory contracts
   - Add `app/memory/models.py` with `MemoryItem`, `MemoryType`, `MemoryNamespace`, `MemorySearchResult`, and extraction result schemas.
   - Add state fields in `FloodGraphState`: `memory_context`, `conversation_summary`, `memory_write_candidates`, `memory_write_result`.
   - Keep memory objects JSON-serializable so checkpoint serialization remains safe.

2. Complete database support
   - Extend `memory_item` with `namespace`, `key`, `content_hash`, `source_session_id`, `embedding vector`, `score`, `status`, `updated_at`, and `expires_at`.
   - Add indexes for namespace lookup, semantic search, dedupe hash, and active records.
   - Add read/update/delete/search methods beside `save_memory_item`.
   - Add `get_latest_conversation_summary` and summary range helpers for `conversation_summary`.

3. Build a `MemoryService`
   - Implement `load_context(user_id, session_id, query)`:
     - recent session summary;
     - top semantic memories;
     - high-importance exact namespace memories;
     - current `conversation_snapshot`.
   - Implement `extract_candidates(state, final_response)` using the existing LLM service with strict JSON output.
   - Implement `upsert_memories(candidates)` with dedupe and importance thresholds.
   - Reuse `app/rag/embedder.py` for embeddings; fall back to keyword search when embedding config is missing.

4. Wire memory into the graph
   - Add a `memory_loader` node after `START` and before `supervisor`.
   - Inject concise `memory_context` into `supervisor`, `conversation_assistant`, `risk_assessor`, and `plan_generator` prompts.
   - Add a `memory_writer` node before `END`, or run the writer as a background task after final response.
   - Prefer background writes for normal chat latency; use hot-path writes only for explicit "记住..." or critical operational decisions.

5. Add short-term checkpointing
   - Option A, no new dependency: keep manual message/session persistence, and treat summaries plus snapshots as short-term memory.
   - Option B, official LangGraph path: add `langgraph-checkpoint-postgres`, create an async checkpointer/store factory, run `setup()` during deployment/startup, and compile the graph with `checkpointer` plus `store`.
   - In either option, invoke/stream with config `{"configurable": {"thread_id": session_id}}` so checkpoints align to existing sessions.

6. Add summarization and pruning
   - After each completed turn, summarize older messages once a threshold is exceeded, for example over 20 messages or over a token budget.
   - Keep recent raw turns plus the latest summary in graph context.
   - Add retention policy for low-importance memories and failed/obsolete operational memories.

7. Expose APIs and admin affordances
   - Add memory inspection endpoints:
     - `GET /api/v1/memory?session_id=...`
     - `GET /api/v1/memory/user`
     - `DELETE /api/v1/memory/{id}`
     - `PATCH /api/v1/memory/{id}` for disable/update.
   - Include memory usage metadata in debug/SSE events only when useful, for example `memory_update` and `memory_context_loaded`.
   - Keep normal end-user responses free of internal memory mechanics.

8. Tests and verification
   - Unit tests for database migration idempotency, dedupe, namespace filtering, and fallback search.
   - Unit tests for memory extraction JSON parsing and rejection of low-value candidates.
   - Integration tests for two-turn same-session recall.
   - Integration tests for cross-session user memory recall.
   - Regression tests ensuring existing `/api/v1/flood/query` and `/api/v1/flood/query/stream` behavior still passes.
   - If official checkpointer is adopted, test `thread_id=session_id` resume and checkpoint cleanup.

## Acceptance criteria

- A new session can recall stable user/operation facts saved from an older session for the same user namespace.
- A long conversation uses summary plus recent turns instead of blindly sending unbounded message history.
- Memory writes are deduplicated and include metadata explaining source session and reason.
- Missing embedding configuration does not break chat; keyword/exact search remains available.
- Existing conversation list/detail APIs continue to return the expected message history.
- Existing tests pass, plus memory-specific tests cover same-session and cross-session recall.

## Risks and mitigations

- Risk: Memory may store transient or sensitive content.
  - Mitigation: require type/importance thresholds, metadata, deletion endpoint, and avoid storing raw credentials or tokens.

- Risk: Memory context can pollute risk assessments with stale facts.
  - Mitigation: mark memory type, source, confidence, update time, and prefer live monitoring data over memory in prompts.

- Risk: Official LangGraph Postgres checkpointer adds dependency and migration surface.
  - Mitigation: phase it after app-level memory is stable, and gate dependency addition as a separate implementation decision.

- Risk: Embedding provider outage affects recall.
  - Mitigation: fallback to namespace + keyword search; memory writes should not block final responses.

## ADR

Decision: Implement app-level memory service first, then optionally add official LangGraph Postgres checkpointer/store.

Drivers:
- Existing app already persists conversations and business snapshots in PostgreSQL.
- The codebase already has embedding and pgvector support.
- Repository guidance discourages new dependencies unless explicitly requested.
- LangGraph's memory model maps cleanly to session-scoped short-term state and namespace-scoped long-term memories.

Alternatives considered:
- Only use last 20 messages. Rejected because it does not provide cross-session memory or long-context management.
- Add only LangGraph checkpointer. Rejected because checkpointing alone is thread-scoped and does not solve long-term semantic recall.
- Replace existing conversation persistence with LangGraph persistence. Rejected because it would risk existing APIs and frontend expectations.

Consequences:
- First phase is low-risk and compatible with current tables.
- Official LangGraph persistence can still be added later without discarding the app memory model.
- Memory behavior becomes testable independently of graph routing.

Follow-ups:
- Decide whether to approve adding `langgraph-checkpoint-postgres` for official checkpointer/store integration.
- Decide retention/privacy policy for memory deletion and cross-user/org namespaces.
- Add frontend memory inspection controls only after backend semantics are stable.
