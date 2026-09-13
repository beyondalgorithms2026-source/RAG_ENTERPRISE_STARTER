# Operations Manual corpus reconciliation

This record documents how the public synthetic Operations Manual v3.2 coexists with the
27 existing Northwind demo sources. It is corpus governance evidence, not a real company
policy.

## Authority and scope

- The manual is the current source for facts it explicitly introduces or amends in its
  v3.2 amendment log.
- Topic-specific documents remain current for details the manual only references or does
  not cover.
- A retrieval answer must cite the source that contains the asserted fact. It may not
  merge incompatible rules silently.
- The original 25-case evaluation is executed before the manual is added to its isolated
  full-stack phase. The manual phase then uses document ACL mode. This preserves the
  approved v1 evidence while still evaluating the combined 90-case suite honestly.

## Reviewed overlaps

| Topic | Existing source | Decision |
|---|---|---|
| Expense approval | `expenses-approval-limits` | Remains the detailed expense-policy authority. Manual Table 2.1 is a broader band delegation matrix and does not remove finance controls. |
| Travel claims | `travel-expense-policy` | Remains authoritative for travel booking, allowances, and its claim deadlines. Manual hospitality controls apply only where explicitly relevant. |
| Information security | `information-security-standard`, `acceptable-use-of-it` | Stricter controls prevail. The manual clarifies that an approved kiosk identity is a device identity, not a shared user account. |
| Data retention | `data-retention-schedule` | Topic-specific schedule remains authoritative for records not listed in Manual Table 7.1. Manual v3.2 governs its explicitly amended cold-chain retention rule. |
| Fleet and incidents | `fleet-and-driver-safety`, `incident-response-procedure` | Existing policies remain detailed procedures; manual sections and Appendix B govern the new operational classifications and cross-references. |
| HR procedures | HR policy documents | The manual's references do not replace the separate grievance, disciplinary, leave, sickness, or whistleblowing procedures. |
| Sensitivity labels | `information-security-standard` and backend ACL | Backend labels remain `public`, `internal`, and `restricted`. Manual “Confidential” material maps to the backend's `restricted` control; it does not create a fourth ACL bypass path. |

## Review result

The manual is public synthetic content. No private-assets source, credential, real person,
client record, or real company information was imported. No unresolved conflict is used
as an expected fact in the curated manual evaluation set; rejected or ambiguous draft
cases remain candidates with a written reason.
