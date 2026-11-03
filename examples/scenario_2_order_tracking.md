# Cenário 2: Rastreamento de Pedido

**Descrição:** Cliente consultando o andamento e o código de rastreamento do seu pedido #1.

**Sessão:** `demo-scenario_2_order_tracking`

---

### Turno 1

**Cliente:**
> Olá, fiz uma compra recente na loja online. Gostaria de saber o status do meu pedido #1.

**Consultor Empório da Música:**

✅ **Detalhes do seu pedido #1**

- **Produto:** Martin D‑28 Dreadnought Natural  
- **Data do pedido:** 15 / 10 / 2025  
- **Data de entrega:** **25 / 10 / 2025**  
- **Código de rastreamento:** **BRAB1234567BR**  
- **Situação atual:** **ENTREGUE**  

Como a entrega ocorreu há mais de 7 dias, o prazo de arrependimento (CDC) já expirou. Contudo, você ainda tem **30 dias de garantia** para eventuais defeitos de fabricação. Caso precise de assistência, basta nos avisar! 🎸

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [RESPONSE TIME] 37071ms  |  [TOKENS] 8658 (Prompt: 8326 / Completion: 332)    │
│ [TOOL INVOKED] get_order_details({'order_id': 1})                             │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 100% Verified                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

### Turno 2

**Cliente:**
> Obrigado! Qual o código de rastreio e quando foi entregue?

**Consultor Empório da Música:**

Claro! O seu pedido #1 foi entregue em **25/10/2025** e o código de rastreamento é **BRAB1234567BR**.  

Se precisar de mais alguma informação – troca, garantia ou outra dúvida – é só me chamar! 🎸

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [RESPONSE TIME] 34038ms  |  [TOKENS] 4252 (Prompt: 4126 / Completion: 126)    │
│ [TOOL INVOKED] Direct Response                                                │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 100% Verified                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

