# Execution Plan — 4 days

Kickoff: 2026-07-02. Each block ends with small, specific commits (English, conventional format).
Principle: working vertical slice early; polish and bonus at the end.

## Day 1 — Foundation + data engineering

- [x] Project scaffold: `pyproject.toml` (uv, pinned deps), `src/emporio/` layout, `.env.example`
      (`OPENAI_API_KEY`, `MODEL`, `EMBEDDING_MODEL`, `REFERENCE_DATE`), `.gitignore`
      (must ignore generated artifacts: `emporio.db`, `chroma/`)
- [x] `etl.py`: CSVs → SQLite (`emporio.db`) — normalize `specs` JSON, validate rows, FK sanity checks
- [x] `db.py` + first tools: `search_products`, `get_product_details` (effective price with active promotions;
      name normalization so "GD20" matches "GD-20")
- [x] `tests/test_etl.py`, `tests/test_tools.py` (happy paths + name normalization)
- Commits: `chore: scaffold project`, `feat: add csv-to-sqlite etl`, `feat: add product search tools`, `test: cover etl and product tools`

## Day 2 — Agent + policies RAG

- [x] `ingest_policies.py`: PDF → per-section chunks → embeddings → ChromaDB
- [x] `retrieval.py` + `search_policies` tool
- [x] `persona.py`: PT-BR instructions grounded in policy §7 + §1; injects "today" date
      (`REFERENCE_DATE` env override — ADR-009)
- [x] `agent.py`: PydanticAI agent wiring all tools, in-memory history
- [x] `cli.py`: chat loop with rich, streaming all events (`run_stream_events`), transcript export to `.md`
- [x] End of day: full vertical slice working (ask price → correct grounded answer)
- Commits: `feat: add policy pdf ingestion and retrieval`, `feat: add agent with persona and tools`, `feat: add cli chat interface`

## Day 3 — Guardrails, Streamlit, example conversations

- [x] `get_order_status`: identifier-first lookup (order id optional), privacy validation + `AuthError` path,
      response joins order items → product names, includes tracking/delivery/notes
- [x] Out-of-scope behavior tuning (off-topic + accessories edge case)
- [x] `app.py`: Streamlit chat — streaming + tool-call expander per response (ADR-006)
- [x] Tests: guardrail cases (wrong identifier, other customer's order), retrieval sanity
- [x] Manual QA against the 4 suggested scenarios from the challenge PDF using verified tool outputs
- [x] Record 3–5 example conversations to `examples/` (≥1 non-trivial: return-policy applied to order 7,
      using `REFERENCE_DATE=2026-02-20`; treat `estimated_delivery` as receipt date because `delivered_at` is absent)
- Commits: `feat: add order status tool with privacy guardrail`, `feat: add streamlit chat with tool-call visibility`, `test: cover privacy guardrail`, `docs: add example conversations`

## Day 4 — README + final review

- [x] README.md (English): run instructions (CLI + Streamlit), decision justifications (distilled from
      `docs/decisions.md`), documented assumptions (REFERENCE_DATE), known limitations + "with more time",
      AI-assistant usage section (Claude Code workflow)
- [ ] Streamlit screenshots for `examples/`
- [x] Clean-copy test: `uv sync --locked`, tests, lint, CLI entry point, and SQLite rebuild from zero
- [ ] Live OpenAI ingestion + CLI/Streamlit smoke test with evaluator-provided API key
- [x] Commit history and deliverables checklist reviewed; external delivery items intentionally remain open
- [ ] Push, verify repo is public, reply to the process e-mail with the link
- Commits: `docs: write readme`, `chore: final polish`

## Buffer / risk notes

- If behind after Day 2: cut Streamlit tool-call expander first (keep plain Streamlit chat), then reduce tests to
  guardrail-critical only. Never cut: README quality, example conversations, privacy guardrail.
- Embedding/API issues fallback: keyword section-matching for policies (documented as limitation).
