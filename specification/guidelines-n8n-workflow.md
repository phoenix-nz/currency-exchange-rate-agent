# n8n Workflow Guidelines

Technical constraints and patterns for building n8n workflow automations. Follow these throughout specification execution.

## Tech Stack

- n8n workflow automation
- Workflow JSON files

## Key Constraints

- `connections` in the JSON reference nodes by `name`, not `id`
- If the solution also requires a CAP application, create CAP FIRST before any n8n workflow
- If an n8n workflow calls an agent, document the agent's interface as a configurable HTTP endpoint (e.g. `{{AGENT_BASE_URL}}`), not as a hard-coded reference
- **NEVER** answer with the n8n URL in the message

## Credentials â NEVER include in workflow JSON

- **NEVER** add a `"credentials"` block to any node in the workflow JSON. Credential blocks embed IDs and names that are instance-specific and will cause import errors on any other n8n instance.
- **NEVER** set `"authentication"` or `"genericAuthType"` parameters on HTTP Request nodes. Leave authentication unconfigured so the user assigns credentials manually in the n8n UI after import.

## Workflow Structure

- All workflow JSON files go in `assets/n8n/workflows/`
- `sourceRoot` in `asset.yaml` MUST be `workflows` (the schema default) â never `n8n/workflows` or any other path
- Each workflow is a single `*.n8n.json` file
- Validate JSON is well-formed after creation

## Integration with Other Assets

- If calling an agent: use configurable HTTP endpoint URL (environment variable or parameter)
- If calling SAP APIs directly: document the API endpoint and authentication requirements
- Keep workflows self-contained and independently deployable
