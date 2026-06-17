# M14 — Tool Actions With Policy Gate

- Added a tool registry for `send_email`, `send_slack`, `create_calendar_event`, and `generate_report`.
- Added role/corpus policy checks before tool invocation.
- Allowed actions are persisted in `tool_invocations`; denied actions are blocked and recorded with denial reason.
- Sensitive external-action tools create approval requests instead of dispatching externally.
- Admin audit events record tool requests, completions, and denials.
