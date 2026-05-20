# Product Requirements Document (PRD)

**Title:** Exchange Rate Update Agent  
**Date:** 2026-05-20  
**Owner:** Finance Operations  
**Solution Category:** n8n Workflow, AI Agent

## Product Purpose & Value Proposition

**Elevator Pitch:**  
Exchange rates in SAP S/4HANA must be accurate daily. This solution automatically fetches official ECB reference rates at 16:30 every day and writes them to S/4HANA — and provides a conversational AI agent for on-demand queries and manual corrections.

**Business Need:**  
Finance teams require up-to-date currency exchange rates in S/4HANA for accurate valuation, reporting, and financial risk management. Manual maintenance is error-prone and creates delays. An automated daily feed from the ECB eliminates this gap, while the AI agent covers edge cases and ad-hoc corrections.

**Product Objectives (Prioritized):**
1. Automatically fetch ECB official reference rates daily at 16:30 and write them to SAP S/4HANA without human intervention.
2. Enable conversational read and manual write of exchange rates via an AI agent.
3. Validate all rate inputs before submission to prevent data quality issues.
4. Provide clear confirmation and an audit trail for every update performed.

## Requirements

### Must-Have Requirements

**R1: Scheduled ECB Rate Ingestion**
- **User Story**: As a finance operations team, I need exchange rates to be fetched automatically from the ECB website at 16:30 every day so that S/4HANA always reflects the latest official reference rates without manual effort.
- **Acceptance Criteria**:
  - Given it is 16:30 on any business day, when the workflow triggers, then it fetches `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`, parses all currency pairs, and upserts each rate into S/4HANA.
  - Given the ECB feed is unavailable, when the fetch fails, then the workflow logs the error and does not write partial data.
- **Priority Rank**: 1

**R2: ECB Rate Parsing**
- **User Story**: As the automated workflow, I need to parse the ECB XML feed so that all EUR-based reference rates are correctly extracted and mapped to S/4HANA fields (ExchangeRateType, SourceCurrency, TargetCurrency, ExchangeRateEffectiveDate, ExchangeRateValue).
- **Acceptance Criteria**:
  - Given the eurofxref-daily.xml is fetched, when parsed, then all currency entries are mapped to valid S/4HANA exchange rate records.
- **Priority Rank**: 2

**R3: Write Rates to S/4HANA (Workflow)**
- **User Story**: As the automated workflow, I need to upsert each parsed rate into S/4HANA via the Currency Exchange Rate OData API so that the system reflects today's ECB rates.
- **Acceptance Criteria**:
  - Given a parsed currency pair and rate value, when the workflow calls the OData API, then the record is created or updated in S/4HANA and the workflow logs the result.
- **Priority Rank**: 3

**R4: Conversational Query of Exchange Rates (AI Agent)**
- **User Story**: As a finance user, I need to query current exchange rates from S/4HANA using natural language so that I can quickly check configured rates without navigating the SAP UI.
- **Acceptance Criteria**:
  - Given a valid currency pair and rate type, when I ask the agent for the current rate, then the agent returns the active rate with its validity date.
- **Priority Rank**: 4

**R5: Manual Create / Update of Exchange Rates (AI Agent)**
- **User Story**: As a finance user, I need to create or correct an individual exchange rate in S/4HANA via the AI agent so that I can handle exceptions not covered by the automated ECB feed.
- **Acceptance Criteria**:
  - Given all required fields (ExchangeRateType, SourceCurrency, TargetCurrency, ExchangeRateEffectiveDate, ExchangeRateValue), when I instruct the agent to update, the agent immediately creates or patches the record without asking for confirmation.
- **Priority Rank**: 5

**R6: Input Validation (AI Agent)**
- **User Story**: As a finance user, I need the agent to validate my input before writing to S/4HANA so that invalid data is caught before submission.
- **Acceptance Criteria**:
  - Given a missing required field, when I submit the request, the agent prompts me to provide it before calling the API.
- **Priority Rank**: 6

## Solution Architecture

**Architecture Overview:**  
Two-component solution on SAP BTP. A cron-triggered n8n workflow handles daily automated ECB ingestion. A Python AI Agent (A2A) handles conversational interaction. Both write to SAP S/4HANA via the same MCP server generated from the `CE_CURRENCYEXCHANGERATE_0001` OData spec.

**Key Components:**
- **n8n Workflow** (`exchange-rate-update-n8n`): Scheduled at 16:30 daily. Fetches ECB XML, parses rates, loops over currency pairs, upserts into S/4HANA via HTTP node.
- **AI Agent (Python/A2A)** (`exchange-rate-update-agent`): Conversational agent. Reads and writes exchange rates in S/4HANA via MCP tools.
- **MCP Server** (generated from `CE_CURRENCYEXCHANGERATE_0001`): Shared integration layer for S/4HANA OData calls, used by both components.

**Integration Points:**
- ECB website `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml` — read-only, daily, XML feed (n8n only).
- S/4HANA `CE_CURRENCYEXCHANGERATE_0001` OData API — read and write exchange rates (both components).

### Agent Extensibility & Instrumentation

**Agent Extensibility:**
- The agent is designed with modular tools to allow future capabilities (e.g., bulk corrections, rate comparison, rate history queries).

**Business Step Instrumentation:**
- All key business steps must emit structured log statements for observability.
- Log pattern: `[MILESTONE_ID].[achieved|missed]: [description]`

### Automation & Agent Behaviour

**Automation Level:** Fully autonomous — both the scheduled workflow and the AI agent operate without human confirmation.

**Actions the system performs without human approval:**
- Fetching ECB rates (n8n workflow, daily at 16:30).
- Parsing and writing all ECB rates to S/4HANA (n8n workflow).
- Reading current exchange rates from S/4HANA (AI agent).
- Validating input parameters (AI agent).
- Creating or updating individual exchange rate records (AI agent).

**Actions that require human review or approval:**
- None — all operations are fully autonomous.

**Model or engine used:** LLM via SAP Generative AI Hub (AI Agent); n8n built-in nodes (workflow).

**Knowledge & data sources accessed:**
- ECB eurofxref-daily.xml — official EUR reference rates, published daily around 16:00 CET.
- SAP S/4HANA Currency Exchange Rate OData API — source of truth for configured rates.

**Tools or connectors invoked (AI Agent):**
- `get_exchange_rates` — lists exchange rates from S/4HANA (read-only).
- `get_exchange_rate` — reads a single rate record (read-only).
- `create_exchange_rate` — creates a new rate record (write, requires confirmation).
- `update_exchange_rate` — updates an existing rate record (write, requires confirmation).

**Guardrails & fail-safes:**
- n8n workflow must not write partial results if the ECB fetch fails.
- Agent must never infer or estimate rate values — all values must be explicitly provided by the user.
- If the S/4HANA API returns an error, both components log the failure and do not silently retry.

## Milestones

### Automated Workflow Milestones

### M1: Scheduled Trigger Fired
- **Description**: The n8n workflow triggers at 16:30 daily.
- **Achieved when**: Cron trigger fires and workflow execution starts.
- **Log on achievement**: `M1.achieved: scheduled trigger fired, workflow started`
- **Log on miss**: `M1.missed: scheduled trigger did not fire`

### M2: ECB Rates Fetched
- **Description**: Workflow retrieves the ECB daily reference rate XML successfully.
- **Achieved when**: HTTP GET to ECB returns a valid XML response with currency data.
- **Log on achievement**: `M2.achieved: ECB rates fetched successfully`
- **Log on miss**: `M2.missed: ECB rates fetch failed, aborting workflow`

### M3: Rates Parsed
- **Description**: Currency pairs and rate values are extracted from the ECB XML feed.
- **Achieved when**: All currency entries are mapped to S/4HANA-compatible rate records.
- **Log on achievement**: `M3.achieved: rates parsed, N currency pairs extracted`
- **Log on miss**: `M3.missed: rate parsing failed or no currencies found`

### M4: S/4HANA Rates Updated (Workflow)
- **Description**: All parsed rates are written to SAP S/4HANA.
- **Achieved when**: All OData POST/PATCH calls return HTTP 200/201.
- **Log on achievement**: `M4.achieved: S/4HANA rates updated, N records written`
- **Log on miss**: `M4.missed: one or more S/4HANA rate updates failed`

### M5: Update Summary Logged
- **Description**: Workflow logs the number of rates updated and any failures.
- **Achieved when**: Summary entry is written to the workflow execution log.
- **Log on achievement**: `M5.achieved: update summary logged`
- **Log on miss**: `M5.missed: summary logging failed`

### Conversational Agent Milestones

### M6: User Request Received
- **Description**: Agent receives and understands a natural language request.
- **Achieved when**: Intent is classified and required parameters are identified.
- **Log on achievement**: `M6.achieved: user request received and intent classified`
- **Log on miss**: `M6.missed: intent classification failed or request not understood`

### M7: Exchange Rate Retrieved
- **Description**: Agent fetches current exchange rate data from SAP S/4HANA.
- **Achieved when**: OData GET call returns a valid response.
- **Log on achievement**: `M7.achieved: exchange rate retrieved from S/4HANA`
- **Log on miss**: `M7.missed: exchange rate retrieval failed or no data returned`

### M8: Update Validated
- **Description**: Agent validates all required parameters before applying changes.
- **Achieved when**: All required fields are present and valid.
- **Log on achievement**: `M8.achieved: input parameters validated successfully`
- **Log on miss**: `M8.missed: input validation failed, user prompted to correct input`

### M9: Exchange Rate Updated (Agent)
- **Description**: Agent successfully creates or updates the rate record in S/4HANA.
- **Achieved when**: OData POST/PATCH returns HTTP 200/201.
- **Log on achievement**: `M9.achieved: exchange rate created/updated in S/4HANA`
- **Log on miss**: `M9.missed: exchange rate update failed, API error returned`

### M10: Confirmation Provided
- **Description**: Agent confirms the operation result to the user.
- **Achieved when**: Confirmation message is returned to the user.
- **Log on achievement**: `M10.achieved: operation result confirmed to user`
- **Log on miss**: `M10.missed: confirmation could not be delivered`
