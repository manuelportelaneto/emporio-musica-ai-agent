# Cenário 4: Interceptação Determinística de Acessórios

**Descrição:** Cliente tentando comprar encordoamento e palhetas; interceptado na camada de entrada com custo zero de LLM.

**Sessão:** `demo-scenario_4_accessory_refusal`

---

### Turno 1

**Cliente:**
> Boa tarde! Vocês vendem encordoamento de nylon para violão e palhetas de 0.73mm?

**Consultor Empório da Música:**

Na Empório da Música somos especialistas exclusivos em instrumentos musicais! Não comercializamos acessórios como cordas, palhetas, cabos, amplificadores ou capas. Se você estiver em Campo Grande, podemos indicar lojas parceiras na região central (Rua 14 de Maio). Posso te ajudar com a escolha de algum instrumento do nosso catálogo hoje?

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [LATENCY] 1ms  |  [TOKENS] 0 (Prompt: 0 / Completion: 0)                      │
│ [TOOL INVOKED] None (Direct/Intercepted)                                      │
│ [GUARDRAILS] Blocked (ACCESSORY_OUT_OF_SCOPE) | Zero LLM Cost                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

### Turno 2

**Cliente:**
> E cabos P10 blindados ou amplificador para guitarra, vocês têm disponível?

**Consultor Empório da Música:**

Na Empório da Música somos especialistas exclusivos em instrumentos musicais! Não comercializamos acessórios como cordas, palhetas, cabos, amplificadores ou capas. Se você estiver em Campo Grande, podemos indicar lojas parceiras na região central (Rua 14 de Maio). Posso te ajudar com a escolha de algum instrumento do nosso catálogo hoje?

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [LATENCY] 0ms  |  [TOKENS] 0 (Prompt: 0 / Completion: 0)                      │
│ [TOOL INVOKED] None (Direct/Intercepted)                                      │
│ [GUARDRAILS] Blocked (ACCESSORY_OUT_OF_SCOPE) | Zero LLM Cost                 │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

