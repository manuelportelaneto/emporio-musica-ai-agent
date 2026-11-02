# Cenário 1: Busca no Catálogo & Condições de Pagamento

**Descrição:** Cliente interessado em violão para iniciantes, comparando preços, desconto no PIX e parcelamento.

**Sessão:** `demo-scenario_1_catalog_search`

---

### Turno 1

**Cliente:**
> Olá! Estou começando a aprender violão e gostaria de ver opções para iniciante, especialmente o Yamaha C40. Vocês têm em estoque e quais são as condições de pagamento?

**Consultor Empório da Música:**

Encontrei excelentes opções no nosso catálogo para você:

• Yamaha C40 Nylon Natural: Preço regular R$ 599.90, à vista no PIX por R$ 569.90 ou parcelado em 6x de R$ 99.98 sem juros.

Lembrando que o pagamento via PIX conta com 5% de desconto à vista! Se estiver em Campo Grande, te convido a passar na nossa loja na Rua 14 de Maio, 3200 para sentir o timbre e a pegada de perto!

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [LATENCY] 14ms  |  [TOKENS] 225 (Prompt: 140 / Completion: 85)                │
│ [TOOL INVOKED] lookup_catalog(query='yamaha c40')                             │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 100% Verified                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

### Turno 2

**Cliente:**
> Esse valor tem desconto no PIX? Consigo parcelar no cartão de crédito?

**Consultor Empório da Música:**

Na Empório da Música facilitamos sua compra! Para pagamento à vista no PIX, você ganha 5% de desconto sobre o valor de tabela (desconto não-cumulativo com itens em promoção). No cartão de crédito, parcelamos em até 12x sem juros (parcelas mínimas: R$ 100 para 7-12x, R$ 80 para 4-6x e R$ 50 para até 3x). Qual instrumento você gostaria de adquirir hoje?

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [LATENCY] 8ms  |  [TOKENS] 170 (Prompt: 110 / Completion: 60)                 │
│ [TOOL INVOKED] query_store_policy(topic='pagamento pix cartão')               │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 100% Verified                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

