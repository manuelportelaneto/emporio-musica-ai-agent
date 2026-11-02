# Cenário 2: Rastreamento de Pedido

**Descrição:** Cliente consultando o andamento e o código de rastreamento do seu pedido #1.

**Sessão:** `demo-scenario_2_order_tracking`

---

### Turno 1

**Cliente:**
> Olá, fiz uma compra recente na loja online. Gostaria de saber o status do meu pedido #1.

**Consultor Empório da Música:**

Localizei seu pedido #1 no sistema! Itens: Martin D-28 Dreadnought Natural (Qtd: 1). Status atual: DELIVERED. Código de rastreamento: BRAB1234567BR. Prazo de 7 dias corridos de arrependimento (CDC) expirado (entregue há 373 dias). Válida apenas a garantia da loja de 30 dias para defeitos de fabricação. Se precisar de suporte adicional, nossa equipe na Rua 14 de Maio, 3200 está à disposição!

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [LATENCY] 8ms  |  [TOKENS] 175 (Prompt: 110 / Completion: 65)                 │
│ [TOOL INVOKED] get_order_details(order_id=1)                                  │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 100% Verified                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

### Turno 2

**Cliente:**
> Obrigado! Qual o código de rastreio e quando foi entregue?

**Consultor Empório da Música:**

Encontrei excelentes opções no nosso catálogo para você:

• Shelby SU-21S Soprano Sunburst: Preço regular R$ 159.90, à vista no PIX por R$ 151.91 ou parcelado em 3x de R$ 53.30 sem juros.
• Kalani KAL-300S Soprano Natural: Preço regular R$ 179.90, à vista no PIX por R$ 170.91 ou parcelado em 3x de R$ 59.97 sem juros.
• Kala KA-15S Soprano Mogno: Preço regular R$ 199.90, à vista no PIX por R$ 189.91 ou parcelado em 3x de R$ 66.63 sem juros.

Lembrando que o pagamento via PIX conta com 5% de desconto à vista! Se estiver em Campo Grande, te convido a passar na nossa loja na Rua 14 de Maio, 3200 para sentir o timbre e a pegada de perto!

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [LATENCY] 14ms  |  [TOKENS] 225 (Prompt: 140 / Completion: 85)                │
│ [TOOL INVOKED] get_order_details(order_id=None), lookup_catalog(query='Obrigado! Qual o cód') │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 100% Verified                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

