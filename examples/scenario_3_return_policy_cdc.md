# Cenário 3: Política de Devolução pelo CDC (7 Dias de Arrependimento)

**Descrição:** Cliente solicitando devolução de um instrumento entregue e verificação das regras do Código de Defesa do Consumidor.

**Sessão:** `demo-scenario_3_return_policy_cdc`

---

### Turno 1

**Cliente:**
> Recebi meu instrumento há 3 dias mas gostaria de saber como funciona para devolver se eu me arrepender da compra online.

**Consultor Empório da Música:**

Para a Grande Campo Grande, temos entrega via motoboy com frete grátis em compras acima de R$ 500 (ou taxa fixa de R$ 35 abaixo desse valor). Envios para outros estados são feitos via Correios (SEDEX/PAC) e Jadlog. Nossa política de trocas segue o Código de Defesa do Consumidor com 7 dias corridos de arrependimento e 30 dias de garantia contra defeitos de fabricação.

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [RESPONSE TIME] 9ms  |  [TOKENS] 150 (Prompt: 95 / Completion: 55)            │
│ [TOOL INVOKED] query_store_policy(topic='Recebi meu instrumen')               │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 100% Verified                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

### Turno 2

**Cliente:**
> E se já tiver passado mais de 7 dias da entrega, ainda posso devolver?

**Consultor Empório da Música:**

Para a Grande Campo Grande, temos entrega via motoboy com frete grátis em compras acima de R$ 500 (ou taxa fixa de R$ 35 abaixo desse valor). Envios para outros estados são feitos via Correios (SEDEX/PAC) e Jadlog. Nossa política de trocas segue o Código de Defesa do Consumidor com 7 dias corridos de arrependimento e 30 dias de garantia contra defeitos de fabricação.

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [RESPONSE TIME] 8ms  |  [TOKENS] 150 (Prompt: 95 / Completion: 55)            │
│ [TOOL INVOKED] query_store_policy(topic='E se já tiver passad')               │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 100% Verified                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

