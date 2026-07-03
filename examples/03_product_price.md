# Product prices and promotion

Demo configuration: `REFERENCE_DATE=2026-02-20`.

## Cliente

Quanto custa o Takamine GD20?

## Assistente

O **Takamine GD20 Dreadnought Natural** custa **R$ 2.199,00** e há 5 unidades em estoque. Ele tem tampo sólido
em cedro, cordas de aço e um timbre quente, especialmente interessante para fingerstyle. Posso comparar com outro
modelo para você?

<details>
<summary>Tool call</summary>

```json
{
  "name": "get_product_details",
  "arguments": {"product_name": "Takamine GD20"}
}
```

</details>

## Cliente

E o Taylor 110e?

## Assistente

O **Taylor 110e Dreadnought Natural** está com **8% de desconto exclusivo**: o preço original é R$ 5.999,00 e
o valor promocional é **R$ 5.519,08**. Temos 4 unidades. É um modelo com tampo sólido em Sitka Spruce e captação
ES2, bem adequado para palco. Quer comparar as especificações dos dois?

<details>
<summary>Tool call</summary>

```json
{
  "name": "get_product_details",
  "arguments": {"product_name": "Taylor 110e"}
}
```

</details>
