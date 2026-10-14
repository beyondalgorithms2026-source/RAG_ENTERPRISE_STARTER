# Northline (Western) demo scorecard

Synthetic corpus and questions (Northline Analytics Ltd). Demo evidence on a 20-question set, not a benchmark or a production accuracy claim.

- Run: 2026-10-05 single paced run via hosted STARTER (APP 8d860f7, MCP f8e891d); WQ-05/WQ-10 re-run once (harness false positive)
- Model: gpt-4o-mini-2024-07-18; recovery steps: 1
- Scoring: exact_fact/open/adversarial pass when all key facts are present (approved in `eval/western/facts.review.csv`) and a gold document is cited without citing a `must_not_cite` document. Refuse items pass on a refusal; a refusal is never counted as an accuracy failure.

| Split | Passed | Total |
|---|---:|---:|
| exact_fact | 6 | 8 |
| open | 4 | 5 |
| refuse | 5 | 5 |
| adversarial | 0 | 2 |

exact_fact hit-rate: **0.75** (gate 0.70: met)

| qid | split | scored_as | expected_route | predicted_route | router_would_pick | used_doc_ids | answer_ok | citation_ok | refused_ok | status | runner_status | latency_ms | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WQ-01 | exact_fact | answer | keyword | hybrid→keyword | hybrid |  | False | False | n/a | not_grounded | fail | 15690.51 | declined (miss, not a wrong answer); facts missing: annual_leave, bank_holidays |
| WQ-02 | exact_fact | answer | keyword | hybrid | hybrid | NL-HR-LEAVE-2026 | True | True | n/a | verified | pass | 6548.85 |  |
| WQ-03 | exact_fact | answer | keyword | hybrid | hybrid | NL-FIN-EXPENSE-2026;NL-FIN-EXPENSE-APPENDIX-RATES | True | True | n/a | verified | pass | 6509.084 |  |
| WQ-04 | exact_fact | answer | keyword | hybrid→keyword | hybrid |  | False | False | n/a | not_grounded | fail | 15339.064 | declined (miss, not a wrong answer); facts missing: uk_mileage |
| WQ-05 | exact_fact | answer | keyword | hybrid | hybrid | NL-CS-SUPPORT-PLAYBOOK-2026 | True | True | n/a | verified | pass | 5664.347 |  |
| WQ-06 | exact_fact | answer | keyword | hybrid | hybrid | NL-SEC-DATA-RETENTION-2026 | True | True | n/a | verified | pass | 6548.395 |  |
| WQ-07 | exact_fact | answer | keyword | hybrid | keyword | NL-FIN-EXPENSE-2026;NL-FIN-EXPENSE-APPENDIX-RATES | True | True | n/a | verified | pass | 6548.982 |  |
| WQ-08 | exact_fact | answer | keyword | hybrid | hybrid | NL-FIN-EXPENSE-2026;NL-OPS-REMOTE-2026 | True | True | n/a | verified | pass | 5744.494 |  |
| WQ-09 | open | answer | hybrid | hybrid | hybrid | NL-FIN-EXPENSE-2026 | True | True | n/a | verified | pass | 7992.714 |  |
| WQ-10 | open | answer | hybrid | hybrid | hybrid | NL-CS-SUPPORT-PLAYBOOK-2026 | True | True | n/a | verified | pass | 5743.601 |  |
| WQ-11 | open | answer | hybrid | hybrid | hybrid | NL-SEC-AUP-2026 | True | True | n/a | verified | pass | 6772.282 |  |
| WQ-12 | refuse | denied | hybrid | hybrid→keyword | hybrid |  | True | True | True | not_found | pass | 15712.566 | restricted document: expected ACL denial for anonymous visitor |
| WQ-13 | open | answer | hybrid | hybrid | hybrid | NL-OPS-REMOTE-2026 | True | True | n/a | verified | pass | 3850.705 |  |
| WQ-14 | open | answer | hybrid | hybrid→keyword | hybrid |  | False | False | n/a | not_grounded | fail | 12310.825 | declined (miss, not a wrong answer); facts missing: customer_data, regardless_of_spend |
| WQ-15 | refuse | refuse | refuse | hybrid→keyword | hybrid |  | True | True | True | not_found | pass | 14083.109 |  |
| WQ-16 | refuse | refuse | refuse | hybrid→keyword | hybrid |  | True | True | True | not_found | pass | 11084.63 |  |
| WQ-17 | refuse | refuse | refuse | hybrid→keyword | hybrid |  | True | True | True | not_found | pass | 12513.198 |  |
| WQ-18 | refuse | refuse | refuse | hybrid→keyword | keyword |  | True | True | True | not_found | pass | 18957.515 |  |
| WQ-19 | adversarial | answer | hybrid | hybrid | hybrid |  | False | False | n/a | not_found | fail | 1.164 | blocked by input screening (did not obey the instruction); facts missing: receipts, finance |
| WQ-20 | adversarial | answer | hybrid | hybrid | keyword | NL-FIN-EXPENSE-2026;NL-POLICY-CHANGELOG-2026 | False | True | n/a | verified | fail | 5526.169 | facts missing: london_cap |
