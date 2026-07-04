# Empório da Música Support Agent

Customer-support agent built in Python for the Artefact AI Engineer technical challenge. It answers Brazilian
customers in PT-BR, queries operational data (CSVs → SQLite) through typed tools, retrieves store policies
(PDF → section-based RAG), and makes its tool-routing decisions visible in both CLI and Streamlit. Design
details and every decision's trade-offs live in [docs/](docs/) — this README covers how to run it and why it
is shaped this way.

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/) and an OpenAI API key.

**0. Install uv** (skip if you already have it):

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart the terminal afterwards (or follow the installer's PATH instructions) so `uv` is on the PATH.

**1. Clone and install the locked environment** (installs Python 3.12 automatically if needed):

```bash
git clone https://github.com/johann0301/artefact_technical_challenge.git
cd artefact_technical_challenge
uv sync --locked
```

**2. Configure your key** — copy the template, then edit `.env` and set `OPENAI_API_KEY`:

```bash
cp .env.example .env
```

**3. Build the local data artifacts** (CSVs → SQLite; policy PDF → embeddings — uses cents of API credit):

```bash
uv run emporio-setup
```

**4. Chat** — Streamlit UI with visible tool calls:

```bash
uv run streamlit run app.py
```

or the terminal chat (`--transcript FILE` exports the conversation to Markdown):

```bash
uv run emporio-chat
```

Configuration (only the key is required):

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | — | Authenticates chat and embedding requests |
| `MODEL` | `openai:gpt-4o-mini` | PydanticAI model identifier |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model for the policy index |
| `REFERENCE_DATE` | System date | ISO date to simulate "today" in date-relative demos |

## Architecture

```text
Customer message
      │
      ▼
CLI / Streamlit ──► PydanticAI agent ──► typed tool selection
                                           ├── catalog/products ──► SQLite
                                           ├── customer orders ───► SQLite
                                           └── store policies ────► ChromaDB
```

Both interfaces share one agent core. Tool descriptions are the routing layer; tools return structured Pydantic
models, and the LLM only selects tools and phrases the grounded result — all SQL is parameterized, no
text-to-SQL is exposed to the model.

### Why these choices

- **Single agent:** four clear intents do not justify an additional router or state graph.
- **PydanticAI:** concise typed tool schemas, validation, provider configuration, and event streaming.
- **`gpt-4o-mini`:** reliable tool calling for cents; the model is a config string, so swapping is a one-line change.
- **SQLite:** deterministic joins and filters with zero infrastructure for 65 products and 20 orders.
- **Section-based RAG + ChromaDB:** the policy manual has coherent numbered sections (fixed-size chunks would
  cut rules in half); local vector search needs no separate service.
- **Streamlit plus CLI:** fast development and transcript capture, plus a visual interface that shows which
  tools the agent called — the "knows when to query data vs policies" behavior, made observable.

Rejected alternatives and at-scale paths are recorded per decision in [docs/decisions.md](docs/decisions.md).

### Prior experience behind this shape

I have shipped something very similar: a luxury-travel concierge that embedded hotel documentation (PDFs) and
used RAG to answer guests and staff — Supabase and the Gemini API there, but the pattern (unstructured
documents, section-aware embedding, retrieval grounding a persona) transfers directly to the store policies here.

A different project taught me where this pattern stops being enough: a multi-agent conversational product where
use cases really required orchestration — LangGraph state graphs with an intent router, per-agent tool
registries, a structured database (Postgres) side by side with a non-structured one (MongoDB for conversation
state/checkpoints), and a conversational test harness (scripted fake user + LLM judge). This challenge, with a
small dataset and four clear intents, sits comfortably on the simple side of that line (ADR-001).

The commit history also shows a FastAPI endpoint and the start of a React front-end being added and later
removed: I considered a custom front-end, but solving the problem simply mattered more, and Streamlit already
demonstrates the property that counts (ADR-010 records the reversal).

### Prompt strategy

The persona instructions (PT-BR, [src/emporio/persona.py](src/emporio/persona.py)) are grounded in the policy
manual itself — §7 defines the official service tone, §1 the store identity — plus five rule families,
tightened after live-model failures (each failure became a live eval scenario):

- **Grounding:** prices, stock, orders, and policy rules must come from tool results; if a tool returns nothing,
  say so — never guess.
- **Scope:** instruments only; the accessory exclusion (strings, cables, pedals…) is enumerated explicitly
  because routing alone matched "cordas de violão" against 7-string guitars. Off-topic gets redirected, not answered.
- **Privacy:** order lookups require the customer's phone or e-mail; the deterministic ownership check lives in
  the tool, not in the prompt.
- **Policy-first:** rule questions are answered from the policies before any identification is requested.
- **Dates:** "today" is injected at session start and the model never does calendar arithmetic — the order tool
  returns `days_since_receipt` computed in code.

## Behavior notes and assumptions

- Only active products are offered; active promotions show original price, discount, and final price.
- Order queries always filter by the matched customer; wrong identifier/order combinations get the same safe
  error, and one duplicated e-mail in the dataset is treated as ambiguous (phone required instead).
- The dataset lacks `delivered_at`, so `estimated_delivery` is used as the provisional receipt date for
  delivered orders — the assistant discloses this. `REFERENCE_DATE` only changes the conversational "today"
  (e.g. `2026-02-20` reproduces the in-window return example); it never rewrites data.
- The agent is deliberately read-only: it explains rules and status but does not execute returns, purchases, or
  stock updates — write actions would need confirmation flows and an order-management integration that the
  dataset does not have.

## Example interactions

Five PT-BR conversations in [examples/](examples/), recorded with `REFERENCE_DATE=2026-02-20`:
catalog search under a budget, store info and the accessories edge case, prices and promotions,
**return policy applied to a real order** (the non-trivial scenario: policy retrieval, live order data, the
in-code day count, and the privacy guardrail refusing another customer's order — all in one conversation),
and order tracking with identification.

## Tests

```bash
uv run pytest              # offline suite; no API calls, no key needed
uv run pytest -m live      # 9 golden behavior scenarios vs the real model (needs key, costs cents)
uv run ruff check src tests app.py
```

The offline suite covers ETL integrity, promotion pricing, normalization, the cross-customer privacy guardrail,
retrieval, agent configuration, and Streamlit startup errors. The live scenarios assert which tools the agent
calls and key facts or refusals in the answers; several encode failures found during manual live review, acting
as persona/routing regression tests. They are stable at temperature 0.1, but wording variance can rarely flip
one assertion — re-run a failed scenario once before treating it as a regression.

## Known limitations and next steps

- Requires an OpenAI key and network access; a keyword-retrieval fallback could support offline use.
- History is in memory per session; no cross-session persistence.
- Nine golden scenarios is a start — production would grow a versioned eval dataset with LLM-judged quality
  dimensions in CI.
- No production hardening: auth, PII masking in logs, tracing, rate limiting, human handoff.
- With more time: order-management API integration (enabling safe write actions), hybrid retrieval with
  reranking, durable sessions, and a real customer channel such as WhatsApp.

## AI coding assistant usage

Two assistants with distinct roles, in a loop:

- **Claude Code running Claude Fable 5** (also a good excuse to put the newly released model through its paces)
  helped structure the documentation around decisions I had already made: mapping the challenge PDF into a
  deliverables checklist and recording each decision as an ADR (rationale + rejected alternatives + at-scale
  notes) **before** implementation. The ADRs later became this README's justification sections.
- **OpenAI Codex** helped with the implementation
  working against the real schemas and installed library APIs, and surfacing dataset edge cases along the way
  (the duplicated customer e-mail, the missing `delivered_at` column). The hands stayed on the wheel: I wrote
  code directly where it was faster to do so, and no generated code was committed without being read, adjusted,
  and tested.
- **Back to Claude** for review, testing, and commits: driving the real model through live scenarios (which
  exposed three persona failures and a date-arithmetic failure — each fix became a permanent `pytest -m live`
  regression scenario), running the suite and lint, and keeping commits small and specific.

Scope reversals (the React/FastAPI experiment) are documented in ADR-010 and visible in the commit history
instead of force-pushed away. Technical choices remain explicit in the repository rather than delegated to the
assistants.

## Project structure

```text
.
├── app.py                    # Streamlit interface (visible tool calls)
├── data/                     # Provided CSVs and policy PDF
├── docs/                     # Deliverables checklist, architecture, ADRs, execution plan
├── examples/                 # Five PT-BR interaction transcripts
├── src/emporio/              # etl, ingest_policies, tools, retrieval, agent, persona, cli
└── tests/                    # Offline suite + opt-in live behavior evals
```
