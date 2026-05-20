# Specification: n8n (exchange-rate-ecb-sync)

> **Guidelines**: Read [guidelines.md](../guidelines.md) and [guidelines-n8n-workflow.md](../guidelines-n8n-workflow.md) before executing ANY tasks below. Follow all constraints described there throughout execution.

## Basic Setup

- [ ] Read `product-requirements-document.md` and `intent.md`

## Workflow: exchange-rate-ecb-sync

Automated daily workflow that fetches ECB reference rates at 16:30 and writes them to SAP S/4HANA.

### Nodes to implement

- [ ] **Cron Trigger** — Schedule node firing daily at 16:30 (CET/local time)
- [ ] **HTTP Request: Fetch ECB Rates** — GET `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`; no authentication; returns XML
- [ ] **XML Parser** — Parse the fetched XML response to extract currency entries from `gesmes:Envelope > Cube > Cube > Cube` elements, producing a list of `{currency, rate}` objects
- [ ] **Set Effective Date** — Set today's date formatted as `YYYY-MM-DD` as `ExchangeRateEffectiveDate`
- [ ] **Split In Batches / Loop** — Iterate over the parsed currency list, one currency pair per iteration
- [ ] **HTTP Request: Upsert Rate in S/4HANA** — For each currency entry, call the S/4HANA Currency Exchange Rate OData API:
  - Base URL: configurable via workflow parameter `S4_BASE_URL` (e.g. `https://<tenant>.s4hana.cloud.sap/sap/opu/odata/sap/API_EXCHANGERATE`)
  - Try POST `/CurrencyExchangeRate` to create; on 409 conflict, fall back to PATCH `/CurrencyExchangeRate/{ExchangeRateType}/{SourceCurrency}/{TargetCurrency}/{ExchangeRateEffectiveDate}`
  - Payload fields: `ExchangeRateType` (default `"M"`), `SourceCurrency` (`"EUR"`), `TargetCurrency` (from ECB entry), `ExchangeRateEffectiveDate`, `ExchangeRateValue`
  - Do NOT configure credentials in JSON; leave authentication unconfigured for manual setup in n8n UI
- [ ] **Error Handler** — If ECB fetch fails (non-2xx response), stop workflow immediately and log `M2.missed: ECB rates fetch failed, aborting workflow`
- [ ] **Summary Log** — After the loop completes, set a summary item logging count of processed records and any errors: `M4.achieved: S/4HANA rates updated, N records written` / `M4.missed: one or more S/4HANA rate updates failed`

### Milestone logging (n8n Set nodes or log notes)

- [ ] M1 log: `M1.achieved: scheduled trigger fired, workflow started` — at workflow start
- [ ] M2 log: `M2.achieved: ECB rates fetched successfully` — after successful HTTP GET
- [ ] M2 miss: `M2.missed: ECB rates fetch failed, aborting workflow` — in error handler
- [ ] M3 log: `M3.achieved: rates parsed, N currency pairs extracted` — after XML parse
- [ ] M3 miss: `M3.missed: rate parsing failed or no currencies found` — if parse returns empty
- [ ] M4 log: `M4.achieved: S/4HANA rates updated, N records written` — after loop completion
- [ ] M5 log: `M5.achieved: update summary logged` — final node

### Output

- [ ] Write workflow JSON to `assets/n8n/workflows/exchange-rate-ecb-sync.n8n.json` using the `n8n-workflow` skill
- [ ] Ensure `connections` reference nodes by `name`, not `id`
- [ ] Validate workflow JSON is well-formed
