# Order tracking with customer identification

Demo configuration: `REFERENCE_DATE=2026-02-20`.

## Cliente

Onde está meu pedido?

## Assistente

Para consultar sem expor dados de outro cliente, preciso do telefone ou e-mail usado na compra. O número do pedido
é opcional.

No tool was called before customer identification.

## Cliente

Usei o e-mail anacarol.ferreira@coldmail.com.

## Assistente

Encontrei o pedido 8, com um **Kala KA-C Concert Mogno**. Ele está **enviado**, com entrega estimada para
28/02/2026. O código de rastreamento é **BRJL5544332BR**. Posso ajudar com mais alguma informação sobre o pedido?

<details>
<summary>Tool call</summary>

```json
{
  "name": "get_order_status",
  "arguments": {
    "customer_phone_or_email": "anacarol.ferreira@coldmail.com",
    "order_id": null
  }
}
```

</details>
