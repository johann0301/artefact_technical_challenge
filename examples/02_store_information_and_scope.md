# Store information and scope

Demo configuration: `REFERENCE_DATE=2026-02-20`.

## Cliente

Qual é o endereço da loja?

## Assistente

A Empório da Música fica na **Rua 14 de Maio, 3200 — Centro, Campo Grande/MS, CEP 79202-333**.
Quer que eu consulte também o horário de funcionamento?

<details>
<summary>Tool call</summary>

```json
{
  "name": "search_policies",
  "arguments": {"question": "Qual é o endereço da loja?"}
}
```

</details>

## Cliente

E vocês vendem cordas de violão?

## Assistente

A loja trabalha exclusivamente com instrumentos musicais, então não vende acessórios como cordas, palhetas,
cabos, cases, pedais ou amplificadores. Posso ajudar você a encontrar um violão ou outro instrumento.

<details>
<summary>Tool call</summary>

```json
{
  "name": "search_policies",
  "arguments": {"question": "A loja vende cordas de violão?"}
}
```

</details>
