# Exchange Rate Update Agent

AI agent and automated workflow to update exchange rates in SAP S/4HANA

## Business challenge

Finance teams need to maintain accurate and up-to-date currency exchange rates in SAP S/4HANA. Manual updates are time-consuming and error-prone. The solution must (1) automatically fetch official ECB (European Central Bank) reference rates from the ECB website every day at 16:30 and push them into S/4HANA without human intervention, and (2) allow finance users to query and manually correct exchange rates conversationally via an AI agent.

## Key Milestones

### Automated Workflow (n8n)
1. **Scheduled Trigger Fired** — n8n workflow triggers at 16:30 daily.
2. **ECB Rates Fetched** — Workflow retrieves the daily reference rate XML from the ECB website successfully.
3. **Rates Parsed** — Currency pairs and rate values are extracted from the ECB feed.
4. **S/4HANA Rates Updated** — All parsed rates are written to SAP S/4HANA via the Currency Exchange Rate OData API.
5. **Update Summary Logged** — Workflow logs the number of rates updated and any failures.

### Conversational Agent (AI Agent)
6. **User Request Received** — Agent receives a natural language request to read or update exchange rates.
7. **Exchange Rate Retrieved** — Agent fetches current exchange rate data from SAP S/4HANA.
8. **Update Validated** — Agent validates new rate values before applying changes.
9. **Exchange Rate Updated** — Agent successfully creates or updates a record in S/4HANA.
10. **Confirmation Provided** — Agent confirms the operation result to the user.

## Business Architecture (RBA)

### End-to-End Process

Finance (E2E)

### Process Hierarchy

```
Finance (E2E)
└── Manage Treasury (generic)
    └── Manage payment, cash and risk (BPS-414)
        └── Analyze and implement treasury procedures and policies
        └── Manage financial risks
```

### Summary

Updating exchange rates maps to the Finance E2E process under "Manage Treasury", specifically the "Manage payment, cash and risk" sub-process covering FX rate management and financial risk controls.

## Fit Gap Analysis

| Requirement (business) | Standard asset(s) found | API ORD ID | MCP Server ORD ID | Gap? | Notes / assumptions |
| ---------------------- | ----------------------- | ---------- | ----------------- | ---- | ------------------- |
| Automated daily ECB rate fetch at 16:30 | — | — | — | Yes | No standard SAP product covers scheduled ECB ingestion; n8n workflow required |
| Parse ECB XML reference rate feed | — | — | — | Yes | ECB publishes eurofxref-daily.xml; custom HTTP node in n8n parses XML |
| Read current exchange rates from S/4HANA | SAP S/4HANA Cloud (Financial Risk Management) | `sap.s4:apiResource:CE_CURRENCYEXCHANGERATE_0001:v1` | — | No | OData API available; no MCP server; custom MCP translation file required |
| Create / update exchange rate records | SAP S/4HANA Cloud (Financial Risk Management) | `sap.s4:apiResource:CE_CURRENCYEXCHANGERATE_0001:v1` | — | No | Same OData API supports PATCH/POST operations; used by both n8n and AI agent |
| Conversational agent interface for FX queries and manual corrections | — | — | — | Yes | No standard SAP agent covers this; custom AI Agent required on BTP |

### Key findings

- A **scheduled n8n workflow** running at 16:30 daily is the correct mechanism for autonomous ECB rate ingestion — fixed schedule with no open-ended reasoning needed.
- The **ECB daily reference rates** are published as XML at `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`; all rates are EUR-based.
- The **Currency Exchange Rate OData API** (`CE_CURRENCYEXCHANGERATE_0001`) is the write target for both the n8n workflow and the AI agent.
- No MCP server exists for this API; an MCP translation file must be generated.
- The **AI Agent** handles on-demand conversational queries and manual corrections that fall outside the automated daily cycle.
- Solution category is updated to **n8n Workflow, AI Agent** to reflect both components.

## Recommendations

### Exchange Rate Update — Automated Workflow + AI Agent

#### Executive Summary

n8n workflow fetches ECB rates daily at 16:30; AI agent handles conversational queries

#### Recommended Solution

Two-component solution on SAP BTP:
1. **n8n Workflow** — Cron-triggered daily at 16:30, fetches the ECB eurofxref-daily.xml feed, parses all currency pairs, and upserts each rate into SAP S/4HANA via the Currency Exchange Rate OData API.
2. **AI Agent (Python/A2A)** — Conversational agent that allows finance users to query current rates and manually create or update individual records in S/4HANA. Uses the same OData API via an MCP translation file.

Both components share the same MCP server generated from the `CE_CURRENCYEXCHANGERATE_0001` OData spec.

#### Recommended solution category

n8n Workflow, AI Agent

#### Intent fit
95%
