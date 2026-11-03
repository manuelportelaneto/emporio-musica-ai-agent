# Cenário 2: Rastreamento de Pedido

**Descrição:** Cliente consultando o andamento e o código de rastreamento do seu pedido #1.

**Sessão:** `demo-scenario_2_order_tracking`

---

### Turno 1

**Cliente:**
> Olá, fiz uma compra recente na loja online. Gostaria de saber o status do meu pedido #1.

**Consultor Empório da Música:**

Localizei seu pedido #1 no sistema! Itens: Martin D-28 Dreadnought Natural (Qtd: 1). Status atual: DELIVERED. Código de rastreamento: BRAB1234567BR. Prazo de 7 dias corridos de arrependimento (CDC) expirado (entregue há 373 dias). Válida apenas a garantia da loja de 30 dias para defeitos de fabricação.

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [RESPONSE TIME] 12ms  |  [TOKENS] 175 (Prompt: 110 / Completion: 65)          │
│ [TOOL INVOKED] get_order_details(order_id=1)                                  │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 100% Verified                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

### Turno 2

**Cliente:**
> Obrigado! Qual o código de rastreio e quando foi entregue?

**Consultor Empório da Música:**

Para consultar os detalhes do seu pedido com segurança, você poderia me informar o número do pedido ou o seu telefone de cadastro com DDD?

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [RESPONSE TIME] 11ms  |  [TOKENS] 135 (Prompt: 90 / Completion: 45)           │
│ [TOOL INVOKED] get_order_details(order_id=None)                               │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 100% Verified                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

