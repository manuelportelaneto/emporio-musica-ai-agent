# Cenário 1: Busca no Catálogo & Condições de Pagamento

**Descrição:** Cliente interessado em violão para iniciantes, comparando preços, desconto no PIX e parcelamento.

**Sessão:** `demo-scenario_1_catalog_search`

---

### Turno 1

**Cliente:**
> Olá! Estou começando a aprender violão e gostaria de ver opções para iniciante, especialmente o Yamaha C40. Vocês têm em estoque e quais são as condições de pagamento?

**Consultor Empório da Música:**

🎸 **Yamaha C40 Nylon Natural**  

- **Preço de tabela:** R$ 599,90  
- **Desconto PIX (5 % à vista):** R$ 569,90  
- **Parcelamento no cartão:** até **6×** de R$ 99,98 sem juros (o modelo permite até 6 parcelas; caso queira mais parcelas, o valor mínimo por parcela deve ser respeitado – R$ 100 a partir de 7×, R$ 80 de 4 a 6×, R$ 50 até 3×).  

**Estoque:** Temos 12 unidades disponíveis, pronto para envio ou retirada.

Se quiser avançar com a compra, preciso apenas do seu **nome** e **telefone (DDD + número, só números)** para registrar seu pedido e calcular o frete. Caso prefira experimentar o violão antes, fique à vontade para nos visitar na loja física (Rua 14 de Maio, 3200 – Centro, Campo Grande/MS).  

Como posso ajudar a seguir? 😊

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [RESPONSE TIME] 6774ms  |  [TOKENS] 8640 (Prompt: 8268 / Completion: 372)     │
│ [TOOL INVOKED] lookup_catalog({'in_stock_only': True, 'query': 'Yamaha C40'}) │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 67% Verified                   │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

### Turno 2

**Cliente:**
> Esse valor tem desconto no PIX? Consigo parcelar no cartão de crédito?

**Consultor Empório da Música:**

Sim! O Yamaha C40 tem **5 % de desconto** no pagamento à vista via **PIX**, passando de R$ 599,90 para **R$ 569,90**.

No **cartão de crédito** você pode parcelar em até **12× sem juros**, respeitando as parcelas mínimas da loja:

- **1 a 3×** – parcela mínima de **R$ 50**  
- **4 a 6×** – parcela mínima de **R$ 80** (ex.: 6× R$ 94,98)  
- **7 a 12×** – parcela mínima de **R$ 100** (ex.: 10× R$ 56,99)

Como o valor com desconto é R$ 569,90, as opções mais comuns são:

- **6× R$ 94,98** (sem juros)  
- **8× R$ 71,24** (sem juros)  
- **12× R$ 47,49** (não atende à parcela mínima de R$ 100, então o máximo aqui seria 6× ou 7×, dependendo da sua preferência).

Se quiser avançar com a compra, preciso apenas do **seu nome** e do **telefone (DDD + número, só números)** para registrar o pedido e calcular o frete. Caso prefira experimentar o violão antes, pode nos visitar na loja física (Rua 14 de Maio, 3200 – Centro, Campo Grande/MS).  

Como deseja prosseguir? 🎶

```text
┌─ [TELEMETRY & AUDIT HUD] ───────────────────────────────────────────────────────┐
│ [RESPONSE TIME] 34527ms  |  [TOKENS] 4721 (Prompt: 4233 / Completion: 488)    │
│ [TOOL INVOKED] Direct Response                                                │
│ [GUARDRAILS] Scope Passed | Factual Grounding: 100% Verified                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

