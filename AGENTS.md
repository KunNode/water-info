# AGENTS.md

Repository instructions for coding agents working in `/project/code-work`.

This repo contains a flood-control emergency management system with three main applications:

- `water-info-platform/`: Spring Boot 3.2 / Java 17 backend, MyBatis-Plus, Flyway, PostgreSQL, Redis.
- `water-info-ai/`: FastAPI / LangGraph Python 3.11 AI service, RAG, memory, and risk workflows.
- `water-info-admin/`: Vue 3 / TypeScript / Vite / Element Plus admin frontend.
- Root `docker-compose.yml` runs PostgreSQL, Redis, platform, AI service, admin, and Nginx.

## Project Commands

Run commands from the relevant subdirectory unless noted.

Backend:

```bash
cd water-info-platform
mvn clean compile
mvn test
mvn test -Dtest=StationServiceTest
mvn spring-boot:run -Dspring-boot.run.profiles=dev
```

AI service:

```bash
cd water-info-ai
uv sync --extra dev
cp .env.example .env
uv run python -m app.main
uv run pytest tests/ -v
uv run ruff check app/ tests/
uv run ruff format app/ tests/
```

Frontend:

```bash
cd water-info-admin
npm install
npm run dev
npm run build
npm run lint
npm run format
npm run test
```

Whole stack:

```bash
cp water-info-ai/.env.example water-info-ai/.env
docker-compose up -d --build
docker-compose logs -f
docker-compose down
```

## Project Notes

- Keep Java API, Python AI service, and Vue admin changes aligned when modifying shared contracts.
- The AI service can read PostgreSQL directly for analysis, but writes that require business-rule consistency should go through the Java platform API.
- Flyway migrations live in `water-info-platform/src/main/resources/db/migration/`; new migrations should use the next unused `V{N}__description.sql` version. Historical gaps exist.
- Default local credentials and secrets in README/docker files are for local development only. Do not add real secrets to the repo.
- Demo scripts live in `scripts/demo/` and assume the local stack/API endpoints are available.

## Coding Behavior

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
