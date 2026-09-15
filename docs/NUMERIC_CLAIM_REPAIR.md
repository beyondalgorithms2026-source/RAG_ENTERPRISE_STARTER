# Bounded numeric-claim repair candidate

Owner approved implementation on 15 September 2026. This is an opt-in candidate,
not an approved v2 baseline or a deployed visitor feature.

## Contract

`ANSWER_NUMERIC_CLAIM_REPAIR_ENABLED=false` remains the default. Concrete binary
threshold/definition questions use the existing pinned OpenAI snapshot. Ordinary
lookups retain their existing path. Unsupported providers are not silently swapped.
No dependency, embedding, database or ACL change occurs.

A small source-bound catalog is derived from already SQL-authorized context.
Only explicit comparators, finite decimals, EUR, percentages, Celsius and elapsed
durations are supported. Calendar/Working-Day arithmetic and silent unit conversion
are refused. Source-derived binding IDs are not eval IDs or expected answers. The
model selects relevant bindings but cannot rewrite values, units or operators.

Decimal arithmetic checks each comparison and conclusion. Outside-range checks
preserve inclusive endpoints and coupled duration. A failed necessary duration can
establish No despite a later recovery reading; a positive duration alone cannot
prove an abstract outside-range trigger. Conflicting observations without that
necessary-condition proof and unproved alternative triggers are refused.

There are at most two generation attempts: structured primary and one
contradiction-only repair. Unsupported extraction or ambiguity returns safe
not-found without generic repair loops. Provider, timeout and malformed-output
failures remain infrastructure failures. REST `/ask` uses the existing HTTP 503
`detail.error/message` shape; streaming propagates a fixed sanitized service
exception rather than an apparent quality result.

Released explanations are rendered from validated comparisons and actual source
quotes, not unchecked model prose. Existing citation, approval, audit and grounding
paths still apply. Numeric requests bypass semantic-cache reads/writes. Internal
claims/prompts do not enter public response fields; only the isolated synthetic
diagnostic runner retains sanitized claim outputs for failure analysis.

Immutable prompt history retains numeric-claims versions 1.0.0 and 1.1.0. Version
1.1.0 is registered/hash-checked. Conditional metadata preserves original v1
metadata while the feature is disabled.

## Verification and limitations

Mechanism tests cover numeric boundaries, decimals, four/five/six minutes, range
endpoints, joint conditions, wrong conclusions despite correct numbers, malformed
claims, quotes/citations, unavailable providers, timeout, exhaustion, safe HTTP
errors and ordinary-question compatibility. Fakes do not prove live quality or ACL.

Real STARTER-only checks in isolated Docker corrected OM-044 (No, four minutes
fails the more-than-five-minute trigger) and OM-046 (Yes, €260,000 exceeds
€250,000). Final targeted checks used one generation call each. Supabase was
untouched. Boundary diagnostics and canonical answer-side grading are separate
from full-stack calibration.

The equality diagnostic correctly returned No at exactly five minutes (one
repair); six minutes correctly returned Yes (one primary call). The first
canonical regrade still flagged a concept judgement and the omitted full
classification label. Literal table-row labels are now preserved in the catalog
to prevent losing classification identity. Final canonical scores must be
verified rather than inferred from correct arithmetic; no baseline is promoted.

Early contracts refused unverifiable claims; a larger schema answered correctly
but consumed excessive tokens. Compact deduplicated bindings replaced it. Final
targeted input counts: OM-044 4,141; OM-046 2,670. Estimated costs: $0.000669 and
$0.000449. Single samples are not p95 guarantees. OM-044 exceeds the plan's 20%
input-token review limit versus the preceding 2,804-token diagnostic. Matched
36-case performance verification and explicit review are required before
activation, especially when a repair adds a second call.

Release still requires full-stack verification, ten stable calibration runs,
refusals/RT-06, outstanding nonnumeric fixes, performance review and baseline
approval. No baseline is automatically overwritten. Targeted passes alone do not
authorize deployment.
