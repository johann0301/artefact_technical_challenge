# Empório da Música Support Agent

Customer-support agent built in Python for the Artefact AI Engineer technical challenge. It answers Brazilian
customers in PT-BR, queries operational data through typed tools, retrieves store policies through a small RAG
pipeline, and makes its tool-routing decisions visible in both CLI and Streamlit.

## What it demonstrates

- A single PydanticAI agent routes between catalog, product, order, and policy tools.
- Six CSV files are validated and rebuilt into a local SQLite database.
- The policy PDF is split by its 25 meaningful headings, embedded, and stored in local ChromaDB.
- Product and order queries use parameterized SQL; no text-to-SQL is exposed to the model.
- Order data requires an unambiguous customer phone or e-mail and never returns another customer's order.
- Streamlit shows tool names and arguments without exposing private chain-of-thought.
- Conversation history is preserved in memory for follow-up questions within one session.
- Nine live golden scenarios (`pytest -m live`) guard tool routing, grounding, and the privacy guardrail
  against prompt or model regressions.

The detailed design and trade-offs are documented in [Architecture](docs/architecture.md) and
[Technical Decisions](docs/decisions.md).

## Quick start

### Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- An OpenAI API key with access to the configured chat and embedding models
- Internet access during dependency installation, policy ingestion, and chat requests

### 1. Install the locked environment

```bash
git clone https://github.com/johann0301/artefact_technical_challenge.git
cd artefact_technical_challenge
uv sync --locked
```

`uv` reads `.python-version` and installs Python 3.12 automatically when needed. `uv.lock` is committed so the
same dependency graph is used on the evaluator's machine.

### 2. Configure the model provider

```bash
cp .env.example .env
```

Edit `.env` and provide your key:

```dotenv
OPENAI_API_KEY=your-key-here
MODEL=openai:gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
REFERENCE_DATE=
```

Only `OPENAI_API_KEY` is required. The other values have defaults. `.env` is ignored by Git.

### 3. Build local data artifacts

```bash
uv run emporio-setup
```

This command:

1. validates and loads all supplied CSVs into `emporio.db`;
2. extracts the policy PDF into section-level chunks;
3. creates embeddings and persists them under `chroma/`.

Both generated paths are ignored by Git and can be rebuilt at any time. The embedding step uses a small amount
of OpenAI API credit.

### 4. Run an interface

CLI:

```bash
uv run emporio-chat
```

CLI with transcript export:

```bash
uv run emporio-chat --transcript examples/my-session.md
```

Streamlit:

```bash
uv run streamlit run app.py
```

## Configuration

| Variable | Required | Default | Purpose |
| --- | ---: | --- | --- |
| `OPENAI_API_KEY` | Yes | — | Authenticates chat and embedding requests |
| `MODEL` | No | `openai:gpt-4o-mini` | PydanticAI model identifier |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | Embedding model used by the policy index |
| `REFERENCE_DATE` | No | System date | ISO date (`YYYY-MM-DD`) for reproducible date-relative demos |

To reproduce the return-window example:

```dotenv
REFERENCE_DATE=2026-02-20
```

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

The interfaces share one agent core. Tool descriptions are the routing layer. Tool results are structured
Pydantic models, and the LLM is responsible only for selecting a tool and phrasing the grounded result.

### Why these choices

- **Single agent:** four clear intents do not justify an additional router or state graph.
- **PydanticAI:** concise typed tool schemas, validation, provider configuration, and event streaming.
- **`gpt-4o-mini` via OpenAI API:** reliable tool calling at negligible cost — the whole challenge runs for
  cents, and the evaluator most likely already has a key. The model is a config string (`MODEL` env var), so
  revisiting the choice is a one-line change.
- **SQLite:** deterministic joins and filters with no external infrastructure for 65 products and 20 orders.
- **Section-based RAG:** the policy manual already has coherent numbered sections, so fixed-size chunks would cut
  rules unnecessarily.
- **ChromaDB persistent client:** local vector search without requiring a separate service.
- **Streamlit plus CLI:** fast development and transcript capture, plus an evaluator-friendly visual interface.

Rejected alternatives and scale-up paths are recorded in [docs/decisions.md](docs/decisions.md).

### Prompt strategy

The persona instructions (PT-BR, [src/emporio/persona.py](src/emporio/persona.py)) are grounded in the store's
own policy manual: §7 defines the official service tone ("acolhedor, informal e profissional") and §1 defines
the store identity. On top of the persona, the instructions encode five kinds of rules:

- **Grounding:** prices, stock, orders, and policy rules must come from tool results; when a tool returns
  nothing, say so — never guess. Tool descriptions themselves act as the routing layer.
- **Scope:** the store sells instruments only; the accessory exclusion (strings, picks, cables, cases, pedals,
  amps) is enumerated explicitly because live testing showed routing alone matched "cordas de violão" against
  7-string guitars. Off-topic questions are redirected without answering their content.
- **Privacy:** order lookups require a customer phone or e-mail before the tool is called; the deterministic
  ownership check lives in the tool itself, not in the prompt.
- **Policy-first answers:** questions about rules are answered from the policies before any identification is
  requested; identification is only needed to apply a rule to a specific order.
- **Dates:** "today" is injected at session start, and the model is forbidden from doing calendar arithmetic —
  the order tool provides `days_since_receipt` computed in code, and the model only compares it against the
  policy window.

Rules were added and tightened based on live-model failures, and each failure became a scenario in the live
eval suite (see below).

## Data and privacy behavior

- Prices are stored as integer cents and formatted by the assistant in BRL.
- Only active, in-stock products appear in catalog searches. A direct product lookup can still explain that an
  active product is out of stock.
- Active promotions are applied before price filters and are never cumulative.
- Phone numbers, e-mails, and product names are normalized before deterministic lookup.
- Day counts for date-based policy rules (`days_since_receipt`) are computed in code against the reference
  date; the model compares numbers against policy windows but never does calendar arithmetic.
- An order query always filters by the matched `customer_id`. Unknown customers and wrong customer/order
  combinations receive the same safe error.
- The source data contains one duplicated customer e-mail. That e-mail is considered ambiguous and returns no
  orders; the customer must use the unique phone number instead.

## Assumptions

1. The supplied dataset is treated as a snapshot of a fictional live operation.
2. The data has no actual `delivered_at` field. For delivered orders, `estimated_delivery` is treated as the
   provisional receipt date; the assistant must disclose this and confirm the real date with the customer.
3. `REFERENCE_DATE` changes the conversational date only. It does not rewrite source data.
4. Policy headings are stable for this supplied PDF version (2.1, June 2025).
5. Cross-session history is outside the scope of this single-user prototype.

## Example interactions

The committed examples use verified tool outputs and `REFERENCE_DATE=2026-02-20`. Model wording can vary while
the underlying values and policy rules remain deterministic.

1. [Catalog search under a budget](examples/01_catalog_search.md)
2. [Store information and accessories](examples/02_store_information_and_scope.md)
3. [Product prices and promotion](examples/03_product_price.md)
4. [Return policy applied to an order](examples/04_return_policy_order.md)
5. [Order tracking with identification](examples/05_order_tracking.md)

## Tests and quality checks

The automated suite makes no external API calls. OpenAI responses and embeddings are replaced by deterministic
test doubles where required.

```bash
uv run pytest
uv run ruff check src tests app.py
uv run python -m compileall -q src tests app.py
```

Coverage includes:

- all CSV row counts, foreign keys, JSON parsing, and idempotent rebuilds;
- effective promotional prices, stock filtering, name normalization, and injection-shaped input;
- customer identification, duplicate e-mails, and cross-customer order protection;
- PDF section extraction, local vector ingestion, and policy retrieval;
- agent configuration, persona rules, streaming, history, and Streamlit startup errors.

Live behavior evals (optional, needs `OPENAI_API_KEY`, costs cents):

```bash
uv run pytest -m live
```

Nine golden scenarios assert which tools the agent calls and key facts or refusals in the answers — catalog
filtering, product-name normalization, policy-first answers, address lookup, order status, the cross-customer
privacy guardrail, the accessory refusal, off-topic redirection, and the expired return window. Several encode
failures found during manual live review, so they act as regression tests for the persona and routing. The
scenarios are stable at temperature 0.1, but live-model wording can occasionally flip a single assertion —
re-run a failed scenario once before treating it as a regression.

## Known limitations and next steps

- Chat and policy ingestion require an OpenAI key and network access. A keyword retrieval fallback could support
  offline use.
- Behavior evals cover nine golden scenarios; a production agent would grow this into a versioned eval dataset
  with LLM-judged quality dimensions running in CI.
- Receipt dates are inferred because the source schema lacks `delivered_at`.
- History is in memory only and resets with the process or Streamlit session.
- The agent is deliberately read-only: it explains return rules, prices, and order status but does not execute
  returns, cancellations, purchases, or stock updates. Write actions would require confirmation flows, an
  order-management/inventory integration, and authorization — none of which exist in the supplied dataset.
- There is no production authentication, PII masking in logs, human handoff, tracing, or rate limiting.
- A production version would use an order-management API, durable sessions, hybrid retrieval with reranking,
  observability, automated agent evals, and an authenticated customer channel such as WhatsApp.

## AI coding assistant usage

Claude Code with claude-mem supported the initial architecture and persistent planning context. OpenAI Codex was
then used as a coding collaborator to re-read the supplied files, implement the approved plan, identify dataset
edge cases, and run verification checks. The workflow was iterative: architecture and ADRs were written first;
implementation was split into small commits; generated code was checked against the actual schemas and installed
library APIs; and each phase was gated by tests, linting, and manual inspection.

Concrete examples of how the workflow shaped the result:

- **Docs before code.** Deliverables were mapped from the challenge PDF into a checklist, and every technical
  decision was debated and recorded as an ADR (with rejected alternatives and at-scale notes) before the first
  line of implementation. The ADRs later became this README's justification sections.
- **Live review as a gate.** Driving the real model through test scenarios exposed three persona failures
  (accessory questions matched 7-string guitars; policy questions demanded identification first; off-topic
  questions were answered) and one grounding failure (the model miscounted a February→July gap as within a
  7-day window). Each fix moved logic to the right layer — enumerated scope rules in the persona, date
  arithmetic into deterministic tool code — and each failure became a permanent scenario in `pytest -m live`.
- **Scope reversals recorded, not hidden.** A React front-end and a FastAPI interface were built, reconsidered
  against the repo's own anti-overengineering rule, and removed; ADR-010 and the commit history document the
  full reasoning instead of a force-pushed clean slate.
- **Dataset issues surfaced.** The duplicated customer e-mail, the missing `delivered_at` column, and blank
  optional `.env` values were all found by the assistant and handled explicitly rather than silently.

Technical choices and rejected alternatives remain explicit in the repository rather than being delegated to
the coding assistant.

## Project structure

```text
.
├── app.py                    # Streamlit evaluator interface
├── data/                     # Provided CSVs and policy PDF
├── docs/                     # Architecture, ADRs, plan, and checklist
├── examples/                 # Five PT-BR interaction transcripts
├── src/emporio/
│   ├── agent.py              # PydanticAI tools and event streaming
│   ├── cli.py                # Rich terminal interface and transcript export
│   ├── etl.py                # Atomic CSV-to-SQLite ingestion
│   ├── ingest_policies.py    # PDF section extraction and embeddings
│   ├── retrieval.py          # ChromaDB policy search
│   └── tools.py              # Parameterized catalog and order operations
└── tests/                    # Offline unit/integration tests + opt-in live behavior evals
```

## Challenge documentation

- [Deliverables checklist](docs/deliverables.md)
- [Architecture](docs/architecture.md)
- [Technical decisions](docs/decisions.md)
- [Execution plan](docs/execution-plan.md)
