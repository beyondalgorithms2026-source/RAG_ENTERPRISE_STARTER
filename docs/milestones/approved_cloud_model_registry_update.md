# Approved Cloud Model Registry Update

- Replaced the subscription-only DeepSeek V3.1 cloud option with `gpt-oss:20b-cloud`.
- Added `GPT-OSS 20B Cloud` to the governed LLM registry used by the sandbox model selector.
- Retired the legacy DeepSeek registry entry while preserving historical candidate records.
- Migrated an active legacy DeepSeek selection to the GPT-OSS replacement during profile seeding.
- Updated runtime defaults, environment examples, imported configuration references, and admin smoke coverage.
- Added GPT-OSS prompt-only JSON compatibility, deterministic answer generation, tolerant schema validation, and context-aware repair.
