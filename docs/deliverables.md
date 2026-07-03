# Deliverables Checklist

Mapped from `desafio_tecnico_ai_eng_artefact.pdf`. Deadline: per selection-process e-mail (~2026-07-06, 4 days from kickoff).

## 1. The agent (Python — only hard technical constraint)

- [x] Text-message support agent for "Empório da Música"
- [x] **Persona** aligned with the store's identity and tone (policy PDF §7 has the official service guidelines — use them)
- [x] Receives and answers messages grounded in the provided context
- [x] Knows **when to query data** (availability, prices, order status) vs **when to query policies** (returns, hours, payment methods)
- [x] Handles **out-of-scope questions** gracefully (incl. store-specific edge: they do NOT sell accessories — strings, cables, pedals, cases, amps — policy §1)

## 2. Public GitHub repository

- [ ] Public repo link (delivered by replying to the process e-mail)
- [x] Commit history with real progress — small, specific commits
- [x] No force-push into a single commit
- [ ] **No changes after the deadline**

## 3. README.md

Written in **English** (rest of repo follows CLAUDE.md language rules).

- [x] **Run instructions**: environment setup, model provider config (API key), commands (CLI + Streamlit)
- [x] **Documented assumptions**: dataset treated as live snapshot; `REFERENCE_DATE` override for date-relative demos;
      `estimated_delivery` used as receipt date for delivered orders because `delivered_at` is unavailable (ADR-009)
- [x] **Technical decisions justified**: framework, LLM, retrieval architecture, prompt strategy (source: `docs/decisions.md`)
- [x] **Known limitations** + what I would do with more time
- [x] **AI assistant usage**: Claude Code/claude-mem and OpenAI Codex roles explained in the workflow

## 4. Example interactions (3–5 conversations)

Format: `.md`, `.txt`, or images, committed to the repo. Plan: CLI transcripts exported to `.md` +
Streamlit screenshots (tool-call visibility makes routing observable).

- [x] At least one **non-trivial** scenario: live data query or policy-rule application
- Candidate scenarios (from the PDF + our own):
  - [x] "Quais opções de violões disponíveis custando até R$1000?" — catalog query with filter
  - [x] "Qual o endereço da loja?" — general store info (policies)
  - [x] "Quanto custa o Takamine GD20?" — price lookup (+ active promotion if any)
  - [x] "Me arrependi da minha compra, posso devolver meu pedido?" — return-policy rules applied to a real order (non-trivial: policy + data combined)
  - [x] Order status with customer identification — shows the privacy guardrail
  - [x] Out-of-scope: "Vocês vendem cordas de violão?" → store doesn't sell accessories (policy §1) / or fully off-topic question

## Explicit freedoms granted by the statement

- Not required to use all provided data
- Framework/approach, model/provider, interface, history persistence, data treatment: our call, **justified in README**
- Ambiguities: make a reasonable assumption, document it in the README, move on
