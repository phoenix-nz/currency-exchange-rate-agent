# Specification

> **Guidelines**: Read [guidelines.md](./guidelines.md) before executing ANY tasks below.

Check off items as completed.

## Solution Setup

- [x] Create asset directories: `mkdir -p assets/exchange-rate-update-agent/ assets/n8n/`
- [x] Invoke `setup-solution` skill to create `solution.yaml` and `asset.yaml` files for all assets (agent + n8n workflow)
- [x] Validate all `asset.yaml` and `solution.yaml` files exist and are well-formed

## Asset Implementation

- [x] Execute specification/exchange-rate-update-agent/specification.md (all items)
- [x] Execute specification/n8n/specification.md (all items)
- [x] Cross-implementation compatibility check: verify both the n8n workflow and the AI agent use the same MCP server ORD ID and S/4HANA endpoint configuration; fix any mismatches before proceeding
