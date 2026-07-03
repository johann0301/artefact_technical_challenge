# Catalog search under a budget

Demo configuration: `REFERENCE_DATE=2026-02-20`.

## Cliente

Quais opções de violões disponíveis custando até R$ 1.000?

## Assistente

Encontrei 12 violões disponíveis dentro do seu orçamento. Algumas boas opções são:

- Tagima Memphis AC-39 Nylon Natural — **R$ 429,90** (15 em estoque)
- Rozini RC-104 Nylon Estudante — **R$ 459,90** (10 em estoque)
- Yamaha C40 Nylon Natural — **R$ 599,90** (12 em estoque)
- Yamaha F310 Aço Natural — **R$ 699,90** (14 em estoque)
- Tagima Woodstock Dreadnought Natural — **R$ 899,00** (11 em estoque)

Também há outras opções até R$ 999,00. Você prefere cordas de nylon ou aço?

<details>
<summary>Tool call</summary>

```json
{
  "name": "search_products",
  "arguments": {
    "query": null,
    "category": "Violões",
    "max_price": 1000,
    "min_price": null
  }
}
```

</details>
