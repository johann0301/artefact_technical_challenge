# Execution Plan — 4 days

Kickoff: 2026-07-02. Each block ends with small, specific commits (English, conventional format).
Principle: working vertical slice early; polish and bonus at the end.

## Day 1 — Foundation + data engineering

- [ ] Project scaffold: `pyproject.toml` (uv, pinned deps), `src/emporio/` layout, `.env.example`
      (`OPENAI_API_KEY`, `MODEL`, `EMBEDDING_MODEL`, `REFERENCE_DATE`), `.gitignore`
      (must ignore generated artifacts: `emporio.db`, `chroma/`)
- [ ] `etl.py`: CSVs → SQLite (`emporio.db`) — normalize `specs` JSON, validate rows, FK sanity checks
- [ ] `db.py` + first tools: `search_products`, `get_product_details` (effective price with active promotions;
      name normalization so "GD20" matches "GD-20")
- [ ] `tests/test_etl.py`, `tests/test_tools.py` (happy paths + name normalization)
- Commits: `chore: scaffold project`, `feat: add csv-to-sqlite etl`, `feat: add product search tools`, `test: cover etl and product tools`

## Day 2 — Agent + policies RAG

- [ ] `ingest_policies.py`: PDF → per-section chunks → embeddings → ChromaDB
- [ ] `retrieval.py` + `search_policies` tool
- [ ] `persona.py`: PT-BR system prompt grounded in policy §7 + §1; injects "today" date
      (`REFERENCE_DATE` env override — ADR-009)
- [ ] `agent.py`: PydanticAI agent wiring all tools, in-memory history
- [ ] `cli.py`: chat loop with rich, streaming all events (`run_stream_events`), transcript export to `.md`
- [ ] End of day: full vertical slice working (ask price → correct grounded answer)
- Commits: `feat: add policy pdf ingestion and retrieval`, `feat: add agent with persona and tools`, `feat: add cli chat interface`

## Day 3 — Guardrails, Streamlit, example conversations

- [ ] `get_order_status`: identifier-first lookup (order id optional), privacy validation + `AuthError` path,
      response joins order items → product names, includes tracking/delivery/notes
- [ ] Out-of-scope behavior tuning (off-topic + accessories edge case)
- [ ] `app.py`: Streamlit chat — streaming + tool-call expander per response (ADR-006)
- [ ] Tests: guardrail cases (wrong identifier, other customer's order), retrieval sanity
- [ ] Manual QA against the 4 suggested scenarios from the challenge PDF
- [ ] Record 3–5 example conversations to `examples/` (≥1 non-trivial: return-policy applied to order 7,
      using `REFERENCE_DATE=2026-02-20`; treat `estimated_delivery` as receipt date because `delivered_at` is absent)
- Commits: `feat: add order status tool with privacy guardrail`, `feat: add streamlit chat with tool-call visibility`, `test: cover privacy guardrail`, `docs: add example conversations`

## Day 4 — README + final review

- [ ] README.md (English): run instructions (CLI + Streamlit), decision justifications (distilled from
      `docs/decisions.md`), documented assumptions (REFERENCE_DATE), known limitations + "with more time",
      AI-assistant usage section (Claude Code workflow)
- [ ] Streamlit screenshots for `examples/`
- [ ] Final pass: fresh-clone test (`uv sync` → ingestion → run works from zero), commit history review,
      deliverables checklist (`docs/deliverables.md`) 100% checked
- [ ] Push, verify repo is public, reply to the process e-mail with the link
- Commits: `docs: write readme`, `chore: final polish`

## Buffer / risk notes

- If behind after Day 2: cut Streamlit tool-call expander first (keep plain Streamlit chat), then reduce tests to
  guardrail-critical only. Never cut: README quality, example conversations, privacy guardrail.
- Embedding/API issues fallback: keyword section-matching for policies (documented as limitation).
