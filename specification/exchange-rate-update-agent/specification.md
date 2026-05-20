# Specification: exchange-rate-update-agent

> **Guidelines**: Read [guidelines.md](../guidelines.md) and [guidelines-agent.md](../guidelines-agent.md) before executing ANY tasks below. Follow all constraints described there throughout execution.

## Basic Setup

- [ ] Read the project input (`product-requirements-document.md`, `intent.md`)
- [ ] Bootstrap agent code in `assets/exchange-rate-update-agent/` using skill `sap-agent-bootstrap` (invoke from inside `assets/exchange-rate-update-agent/`, use copy commands — do NOT create files manually)
- [ ] Install dependencies, validate the agent starts and responds at `/.well-known/agent.json`

## Agent Configuration

- [ ] Set the agent name to `Exchange Rate Update Agent`
- [ ] Set the agent description: `An AI agent that reads, creates, and updates currency exchange rates in SAP S/4HANA via natural language conversation.`
- [ ] Set the agent system prompt to instruct the agent to:
  - Execute write operations (create/update) immediately once all required fields are provided — no confirmation step
  - Never infer or estimate rate values — all values must be explicitly provided by the user
  - Validate all required fields (ExchangeRateType, SourceCurrency, TargetCurrency, ExchangeRateEffectiveDate, ExchangeRateValue) before writing
  - Respond clearly with the current rate when queried
  - Confirm every successful write operation with the updated record details
  - Set `top` (or equivalent page-size parameter) to a maximum of 100 on every tool call that accepts it to prevent context overflow; inform the user when this limit is applied

## Tools (via MCP)

All SAP S/4HANA interactions MUST go through the MCP server generated from `specification/exchange-rate-update-agent/api-specs/currency-exchange-rate.json`. No direct HTTP clients.

- [ ] Invoke `mcp-translation-file` skill with the spec at `specification/exchange-rate-update-agent/api-specs/currency-exchange-rate.json`
  - Translation file must expose tools for:
    - `GET /CurrencyExchangeRate` — list / search exchange rates (read-only)
    - `GET /CurrencyExchangeRate/{ExchangeRateType}/{SourceCurrency}/{TargetCurrency}/{ExchangeRateEffectiveDate}` — read a specific rate (read-only)
    - `POST /CurrencyExchangeRate` — create a new exchange rate (write)
    - `PATCH /CurrencyExchangeRate/{ExchangeRateType}/{SourceCurrency}/{TargetCurrency}/{ExchangeRateEffectiveDate}` — update an existing rate (write)
- [ ] Invoke `setup-solution` skill to register the generated MCP server as an asset
- [ ] Wire MCP tool loading in `agent.py` using `get_mcp_tools()` from `mcp_tools.py` (canonical pattern from guidelines-agent.md)
- [ ] Add the MCP server dependency to `assets/exchange-rate-update-agent/asset.yaml` under `requires`

## Business Logic

- [ ] Implement the `get_exchange_rates` capability — agent calls the list/search MCP tool to retrieve rates; supports filtering by source/target currency and rate type
- [ ] Implement the `get_exchange_rate` capability — agent calls the single-record MCP tool using ExchangeRateType, SourceCurrency, TargetCurrency, ExchangeRateEffectiveDate
- [ ] Implement the `create_exchange_rate` capability — agent validates all required fields (ExchangeRateType, SourceCurrency, TargetCurrency, ExchangeRateEffectiveDate, ExchangeRateValue), then immediately calls the POST MCP tool without asking for confirmation
- [ ] Implement the `update_exchange_rate` capability — agent validates all required fields, then immediately calls the PATCH MCP tool without asking for confirmation
- [ ] Implement input validation: if any required field is missing, prompt the user to provide it before proceeding
- [ ] Implement confirmation step: before any write (POST/PATCH) operation, the agent presents a summary and asks the user to confirm

## Business Step Instrumentation

- [ ] Instrument M6 (User Request Received): log `M6.achieved: user request received and intent classified` when intent is resolved; `M6.missed: intent classification failed or request not understood` when not
- [ ] Instrument M7 (Exchange Rate Retrieved): log `M7.achieved: exchange rate retrieved from S/4HANA` on successful GET response; `M7.missed: exchange rate retrieval failed or no data returned` on failure
- [ ] Instrument M8 (Update Validated): log `M8.achieved: input parameters validated successfully` when all required fields are present and valid; `M8.missed: input validation failed, user prompted to correct input` on validation failure
- [ ] Instrument M9 (Exchange Rate Updated): log `M9.achieved: exchange rate created/updated in S/4HANA` on successful POST/PATCH; `M9.missed: exchange rate update failed, API error returned` on API error
- [ ] Instrument M10 (Confirmation Provided): log `M10.achieved: operation result confirmed to user` when confirmation is returned; `M10.missed: confirmation could not be delivered` on failure
- [ ] Add OpenTelemetry custom spans for each business step — extract all business logic from `stream()` into `_run_agent()` helper; instrument that helper only (never wrap `yield` inside `with tracer.start_as_current_span(...)`)
- [ ] Verify `auto_instrument()` is called at top of `main.py` before any AI framework imports

## MCP Mock & Testing

- [ ] Invoke `mcp-mock-config` skill after `mcp-translation-file` and `setup-solution` are complete to generate `mcp-mock.json`
- [ ] `conftest.py` sets only `IBD_TESTING=true`; no branching in application code
- [ ] Write unit test for `get_exchange_rates` tool: mock MCP returns a list of exchange rates; verify agent summarises and returns them
- [ ] Write unit test for `get_exchange_rate` tool: mock MCP returns a single rate; verify agent returns rate details
- [ ] Write unit test for `create_exchange_rate` tool: mock MCP returns success; verify agent confirms the creation
- [ ] Write unit test for `update_exchange_rate` tool: mock MCP returns success; verify agent confirms the update
- [ ] Write unit test for input validation: missing required field should cause agent to prompt user for the missing value, not call the MCP write tool prematurely
- [ ] Write one integration test: end-to-end flow — user asks "What is the EUR to USD rate?", agent retrieves and returns rate details; also test that a create/update request executes immediately without a confirmation prompt
- [ ] Run `pytest` from `assets/exchange-rate-update-agent/` (no args) — fix failures before proceeding
- [ ] Verify exactly 3 decorated functions in `app/agent.py`: `grep -c "^@agent_model\|^@agent_config\|^@prompt_section" assets/exchange-rate-update-agent/app/agent.py` must return 3
- [ ] Run `pytest` again (no args) to produce final `test_report.json`
- [ ] Verify `test_report.json` exists at `assets/exchange-rate-update-agent/test_report.json`

## API Spec

- OData API ORD ID: `sap.s4:apiResource:CE_CURRENCYEXCHANGERATE_0001:v1`
- Spec file: `specification/exchange-rate-update-agent/api-specs/currency-exchange-rate.json`
- Key endpoints used:
  - `GET /CurrencyExchangeRate`
  - `GET /CurrencyExchangeRate/{ExchangeRateType}/{SourceCurrency}/{TargetCurrency}/{ExchangeRateEffectiveDate}`
  - `POST /CurrencyExchangeRate`
  - `PATCH /CurrencyExchangeRate/{ExchangeRateType}/{SourceCurrency}/{TargetCurrency}/{ExchangeRateEffectiveDate}`
