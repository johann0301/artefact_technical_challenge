# Empório da Música — Customer Support Agent (Artefact AI Engineer Challenge)

Python agent that answers customer messages for a fictional musical instrument store,
using structured data (CSVs → SQLite) and unstructured data (store policies PDF → light RAG).

## Repo rules

### Commits

- **Small and specific**: one topic per commit. Never bundle unrelated changes.
- **English**, conventional commits format: `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`.
- Commit history must show real progress (challenge requirement — no single squashed commit, no force-push).
- Do not change anything in the repo after the submission deadline.

### Language

- Code, comments, docs, commits: **English**.
- Agent persona, prompts targeting end users, and example conversations: **PT-BR** (Brazilian customers).

### Engineering principles

- **No overengineering.** Every new layer/abstraction needs a justification anchored in this problem
  (65 products, ~20 orders, ~10-page policy PDF, ~4 clear intents). If a choice would only pay off
  at larger scale, document it in `docs/decisions.md` under "At scale" instead of building it.
- Typed tools with parameterized SQL — never free-form text-to-SQL.
- Privacy guardrail: order lookups require customer identification; never expose other customers' data.

## Key docs

- `docs/deliverables.md` — checklist of everything the challenge PDF requires
- `docs/decisions.md` — ADR-lite records (rationale + rejected alternatives + at-scale notes)
- `docs/architecture.md` — solution design, tools, project layout, prompt strategy
- `docs/execution-plan.md` — 4-day delivery plan

## Source materials

- `desafio_tecnico_ai_eng_artefact.pdf` — challenge statement
- `data/*.csv` — products, customers, orders, order_items, promotions, categories
- `data/políticas_da_loja.pdf` — store policies manual (10 sections)
