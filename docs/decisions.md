# Technical Decisions (ADR-lite)

Each record: **Context → Decision → Why (anchored in this problem) → Rejected alternatives → At scale**.
"At scale" = what I would do in a larger, less-specified context. Kept here so the README can cite it and so the
line between "right-sized" and "overengineered" stays explicit.

---

## ADR-001 — Orchestration: single agent + tool calling (no intent router)

**Context.** The domain has ~4 clear intents: catalog/price queries, order status, policy questions, out-of-scope.
Deadline is 4 days. The challenge evaluates reasoning quality, not architecture size.

**Decision.** One agent with persona instructions and four typed tools. The LLM routes by choosing which tool
to call. Scope handling lives in the instructions + a final fallback behavior.

**Why.**

- Modern tool-calling models route between a handful of well-described tools with high accuracy — an upstream
  intent classifier would duplicate that routing at 2× latency and cost per message.
- Fewer moving parts = fewer failure modes and less code to test in 4 days.
- Sophistication is better spent where this problem actually needs it: tool quality, retrieval, and the privacy
  guardrail on order lookups.

**Rejected alternatives.**

- *Intent router + specialized nodes (LangGraph-style)*: more control and observability per intent, but with 4
  intents and stateless Q&A turns it adds latency, cost, and code without measurable quality gain. Classic
  overengineering for this scope.
- *Manual ReAct loop*: reinvents what tool calling already does natively.

**At scale.** With many intents, stateful multi-turn flows (e.g. booking/reservations), multiple specialized
agents, or human handoff, a LangGraph state machine with an explicit router becomes the right tool: per-node
prompts stay small, flows become testable in isolation, and state checkpointing comes for free. In *this*
challenge it would be overengineering; in a real omnichannel support product it would be my starting point.

---

## ADR-002 — Framework: PydanticAI

**Context.** Need typed tool definitions, provider abstraction, and minimal boilerplate in Python.

**Decision.** PydanticAI as the agent framework.

**Why.**

- Tools are plain decorated Python functions with Pydantic-validated signatures — the LLM sees clean JSON
  schemas, we get runtime validation for free.
- Provider-agnostic model string (`openai:gpt-4o-mini`) — swapping providers is a config change, which is a
  README-friendly property for evaluators.
- Thin abstraction: the agent loop stays legible, no framework magic to explain around.

**Rejected alternatives.**

- *Raw provider SDK*: maximum control, but hand-rolled tool-call loop + schema generation is boilerplate that
  demonstrates little in 2026.
- *LangChain/LangGraph*: heavyweight for a single-agent prototype; abstractions would outnumber the actual logic.

**At scale.** For complex state graphs, multi-agent coordination, or persistent checkpointing, LangGraph earns
its weight (see ADR-001 "At scale").

---

## ADR-003 — Structured data: CSVs → SQLite + typed tools with parameterized SQL

**Context.** 6 small CSVs (65 products with JSON specs, ~50 customers, ~20 orders, 25 promotions, 9 categories).
Questions are predictable: search by category/price/name, price + active promotion, stock, order status.

**Decision.** One ETL script loads the CSVs into a local SQLite database (normalizing the JSON `specs` column and
precomputing joins where useful). Agent tools have **typed parameters** (`search_products(query, max_price,
category)`) and execute **parameterized SQL** internally.

**Why.**

- SQLite gives real joins (products × promotions × categories, orders × items × customers) with zero
  infrastructure — stdlib only.
- Typed tools make queries deterministic: no hallucinated SQL, no silent wrong answers, no injection surface.
- The query space is small and known — flexibility of free-form SQL buys nothing here.
- ETL step demonstrates deliberate data treatment (an explicitly evaluated decision in the challenge).

**Rejected alternatives.**

- *Text-to-SQL tool*: flexible for unpredictable questions, but the failure mode (plausible-looking wrong SQL →
  confidently wrong answer to a customer) is the worst possible one for a support agent.
- *Pandas in-memory filters*: works at this size, but SQL expresses the joins more clearly and the ETL/runtime
  separation is cleaner.

**At scale.** Large schema + unpredictable analytical questions → guarded text-to-SQL (read-only role, query
validation, row limits, self-correction loop) over a real warehouse, or a semantic layer with curated metrics.

---

## ADR-004 — Unstructured data: policy PDF → per-section chunks + embeddings (light RAG)

**Context.** `políticas_da_loja.pdf` is ~10 pages, 10 numbered sections with clear headings (hours, payment,
returns, shipping, promotions, WhatsApp service guidelines, warranty, privacy).

**Decision.** Ingestion script extracts text, chunks **by section heading** (each chunk = one coherent policy with
its section title), embeds chunks (OpenAI embeddings), stores vectors locally (ChromaDB). Agent tool
`search_policies(question)` returns top-k sections.

**Why.**

- Sections are self-contained rules — semantic chunking by heading keeps each rule intact, so retrieved context
  never cuts a rule in half (fixed-size chunking would).
- Embeddings handle customer paraphrase ("me arrependi da compra" → §4.1 right-of-regret) better than keyword
  matching.
- Small corpus (~30–40 chunks) means retrieval is fast, cheap, and easy to eyeball-validate.

**Rejected alternatives.**

- *Whole PDF in the system prompt*: fits (~6–8k tokens) and is tempting, but it pays the token cost on every
  message, dilutes the persona instructions, and demonstrates zero retrieval architecture — an explicitly
  evaluated topic.
- *Keyword/fuzzy section lookup*: no embedding dependency, but brittle to paraphrase, which is the norm in
  customer messages.

**At scale.** Bigger/heterogeneous corpus → hybrid search (BM25 + dense), reranking, retrieval evals
(golden-question set), managed vector DB, and freshness pipelines.

---

## ADR-005 — Model: OpenAI `gpt-4o-mini` (configurable via env)

**Context.** Need reliable tool calling, low cost, and zero friction for an evaluator to run the project.

**Decision.** Default `openai:gpt-4o-mini`, model string configurable via environment variable.

**Why.**

- Best-in-class tool-calling reliability per real relative to cost; the whole challenge runs for cents.
- Evaluators most likely already have an OpenAI key.
- PydanticAI makes the model a config string, so the choice is cheap to revisit.

**Rejected alternatives.**

- *Local model (Ollama)*: free, but tool-calling reliability varies and setup friction for the evaluator is real.
- *Larger models*: no observed need at this task complexity; would raise cost without measurable gain.

**At scale.** Provider fallback chains, per-task model routing (cheap model for routing, stronger for
generation), and cost/latency observability.

---

## ADR-006 — Interface: CLI for dev/transcripts + Streamlit chat with visible tool calls

**Context.** Challenge statement: "CLI, notebook, API, or simple UI — the focus is the agent working correctly."
One of the explicitly evaluated behaviors is that the agent *knows when* to query data vs policies — i.e. its
tool routing. That behavior is invisible in a plain chat transcript unless surfaced deliberately.

**Decision.** Two thin layers over the same interface-agnostic agent core:

- **CLI** (rich-formatted, streaming): development interface; exports session transcripts to `.md`, which doubles
  as the example-conversation deliverable.
- **Streamlit chat** (`app.py`): evaluator-facing UI with streaming and an expander per response showing which
  tools were called and with what arguments (🔧 catalog / 📦 orders / 📖 policies).

**Why.**

- The tool-call expander turns the agent's routing decisions — the exact thing being evaluated — into something
  the evaluator can *watch* instead of trusting.
- CLI keeps the build/debug loop fast and transcript generation trivial.
- Both are additive (~100 lines each) because the agent core is interface-agnostic by construction; no rewrite risk.

**Rejected alternatives.**

- *Chainlit*: renders agent steps natively, but is a niche dependency the evaluator is less likely to know;
  Streamlit achieves the same with one expander.
- *FastAPI + custom front-end*: the statement explicitly de-prioritizes UI investment.

**At scale.** FastAPI service + real channel (WhatsApp webhook), session management, tracing/observability
(LangSmith/OTel) instead of a UI expander.

---

## ADR-007 — Conversation history: in-memory per session

**Context.** Statement: "implement if it makes sense for the UX." The prototype is a single-session chat.

**Decision.** Message history kept in memory for the session (multi-turn context works); no cross-session
persistence. Optionally dump transcripts to file (which doubles as the example-conversation deliverable).

**Why.** Multi-turn coherence within a session is essential UX (follow-up questions about a product just
discussed). Cross-session persistence adds storage + identity complexity with no payoff in a CLI prototype.

**At scale.** Checkpointer in Postgres/Redis keyed by customer, conversation summarization for long histories,
LGPD-compliant retention.

---

## ADR-008 — Guardrails: prompt-level scope + tool-level privacy validation

**Context.** The data includes real-looking PII (names, phones, e-mails) and order history. Policy §9 covers
privacy; §1 states the store sells instruments only (no accessories). Out-of-scope handling is an explicit
requirement.

**Decision.**

- **Scope**: persona instructions define what the agent does/doesn't answer; off-topic questions get a polite
  in-persona redirect. The accessory exclusion (strings, picks, cables, cases, pedals, amps — policy §1) is
  enumerated directly in the instructions: it is a small, stable business rule, and live testing showed that
  relying on tool routing alone made the model match "cordas de violão" against 7-string guitars in the catalog.
- **Privacy**: `get_order_status` requires a customer identifier (phone or e-mail; order id optional — customers
  rarely know it) and the tool itself validates that the identifier matches the order's customer — the check is
  deterministic code, not model goodwill. Tools never return other customers' data.

**Why.** The one guardrail that matters here protects real (fictional) PII, and it must live below the LLM:
prompt instructions can be jailbroken, parameter validation cannot.

**At scale.** Dedicated guardrail layer (input/output classifiers), PII masking in logs, automated red-team
evals, LLM-as-judge regression suite over conversation scenarios.

---

## ADR-009 — Date awareness: inject "today" into the prompt, overridable via `REFERENCE_DATE`

**Context.** The dataset's orders span 2025-10 → 2026-03, but the agent runs at the real current date (2026-07+).
Policy rules are date-relative — §4.1 right of regret is 7 days from receipt, delivery estimates expire. With the
real date, the challenge's own suggested scenario ("me arrependi da minha compra, posso devolver?") would *always*
resolve to "deadline expired", and shipped orders would show stale delivery estimates.

**Decision.** The runtime instructions receive an explicit "today is YYYY-MM-DD" line at session start. It defaults to
the real current date; the `REFERENCE_DATE` env var overrides it (e.g. `REFERENCE_DATE=2026-02-20` to demo order
7 within the regret window). Because the dataset does not provide an actual `delivered_at` timestamp, the prototype
treats `estimated_delivery` as the receipt date for delivered orders and makes that assumption explicit in the answer
and README.

**Why.**

- LLMs don't reliably know the current date; date-relative policy rules need an authoritative anchor.
- The override keeps demos honest: the agent applies the real rule to a simulated "today" instead of us cherry-
  picking data — and the "deadline expired" path stays demonstrable too.
- Treating the dataset as a live snapshot is a reasonable documented assumption, exactly what the statement asks
  for when facing ambiguity.

**Rejected alternatives.**

- *Always use the real date*: correct but makes every return-policy demo a denial; weaker examples.
- *Rewriting the dataset's dates*: mutating provided data is worse than parameterizing time.

**At scale.** Time comes from the order-management system, not the prompt; policy windows computed
deterministically in tools, not by the LLM.

---

## ADR-010 — Third interface: FastAPI SSE endpoint (custom React front-end considered and dropped)

**Context.** The challenge statement lists "API" among the accepted interfaces. The repo already had CLI and
Streamlit over an interface-agnostic core. A custom React front-end (Vite + TS + Tailwind, production build
committed so the evaluator would not need Node) was planned and started, then reconsidered.

**Decision.**

- Keep `src/emporio/api.py`: FastAPI exposing `POST /api/chat` as **Server-Sent Events** (`tool_call`, `text`
  delta, and `done` events) with per-`session_id` in-memory history — the same `run_turn` callbacks the CLI and
  Streamlit consume, serialized over HTTP. Demonstrable with `curl`; `/api/health` for checks.
- **Drop the React front-end.** The statement explicitly de-prioritizes UI ("the focus is the agent working
  correctly"), Streamlit already provides the visual demo with tool-call visibility, and a second chat UI would
  duplicate that at the cost of a Node toolchain, committed build artifacts, and more surface for the evaluator
  to review — complexity without new signal. Reversing the earlier plan mid-way was cheaper than carrying it.

**Why.**

- The API is one small, fully tested module that shows service design (streaming contract, error paths,
  session state) without touching the agent core.
- SSE over WebSockets: the chat is strictly request→streamed-response; SSE is plain HTTP and simpler to test.
- The front-end failed this repo's own bar — every layer needs a justification anchored in this problem, and
  "a second chat UI" had none once Streamlit existed.

**Rejected alternatives.**

- *React + committed `dist/` served by FastAPI*: preserved the uv-only run path, but shipped generated files in
  Git and duplicated the Streamlit demo. Dropped.
- *Next.js*: one page, no SSR/SEO/routing need; would force a Node server or a static export.

**At scale.** A real product gets a real front-end (Next.js or the team's standard) consuming this same SSE
contract, CI-built; WebSockets if bidirectional events appear (typing indicators, human handoff); auth and rate
limiting on the API.

---

## ADR-011 — Agent behavior evals: live golden scenarios as an opt-in pytest marker

**Context.** Deterministic tests cover tools, ETL, and retrieval plumbing, but the agent's *behavior* (tool
routing, grounding, guardrails, scope) was only verified manually. That manual live review caught three real
persona failures (ADR-008), proving this layer regresses silently — any prompt or model change can break it.

**Decision.** `tests/test_behavior_live.py` with ~8 golden scenarios asserting, against the real model:
(1) which tools were called (routing), and (2) key facts or refusals in the answer (grounding/guardrails).
Marked `live` and excluded from the default run; `uv run pytest -m live` runs it when `OPENAI_API_KEY` is set.
Costs cents per run.

**Why.**

- Routing assertions (`search_policies` was called; no catalog tool on an accessory question) are stable at
  `temperature=0.1` and catch exactly the class of bug found manually.
- Opt-in marker keeps the default suite free, fast, and runnable by the evaluator without a key.
- Substring/fact assertions (price, section citation, refusal keywords) are crude but cheap and effective at
  this scale; they encode the live-review findings as permanent regressions tests.

**Rejected alternatives.**

- *LLM-as-judge*: better for nuanced quality, but adds cost, flakiness, and a second prompt to maintain —
  unjustified for 8 scenarios with objectively checkable outcomes.
- *Mocking the model*: tests the harness, not the behavior; routing bugs live precisely in the real model call.
- *No behavior tests*: the manual review already disproved "the prompt is obviously fine".

**At scale.** Versioned eval dataset, LLM-judge for tone/quality dimensions, eval runs in CI on prompt/model
changes, dashboards over time (promptfoo/braintrust-style), and red-team suites for the guardrails.
