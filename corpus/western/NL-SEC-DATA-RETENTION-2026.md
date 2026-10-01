SYNTHETIC

---
id: NL-SEC-DATA-RETENTION-2026
title: Data Retention and Disposal Policy
doc_type: policy
jurisdiction: group
classification: Confidential
effective: 2026-06-01
supersedes: NL-SEC-DATA-RETENTION-2025
synthetic: true
---

# Data Retention and Disposal Policy

## Executive summary

Northline keeps records only for an identified business, contractual, security or legal purpose and disposes of them when that purpose no longer requires retention. The standard periods most often used in retrieval tests are:

- **support tickets: 24 months after ticket closure**;
- **customer and supplier contracts: 7 years after contract end**;
- **unsuccessful candidate CVs and interview records: 12 months after the hiring decision**;
- **finance and accounting records: 7 years after the end of the relevant financial year**;
- **security logs: 12 months**, unless preserved for an incident;
- **recorded support calls: 90 days**;
- **routine product telemetry linked to an identifiable customer/user: 13 months**;
- **rolling backups: 35 days**.

These are Northline operating periods for a synthetic UK-registered B2B SaaS company with a US office and an EU office in the Netherlands. They are not a statement that every organisation must use the same periods.

## Purpose

The purpose of this policy is to keep useful records long enough to serve a defined need while reducing the security and privacy risk of keeping data indefinitely. It provides a default schedule for common Northline systems and explains holds, disposal, backups and exceptions.

The UK and EU GDPR storage-limitation principle requires personal data to be kept no longer than necessary for the purposes for which it is processed. Northline therefore treats retention as a purpose-based control rather than an instruction to keep everything “just in case”.

## Scope

This policy applies to records created, received or stored by Northline Analytics Ltd and its UK, US and Netherlands operations, including data held in SaaS systems, databases, file storage, email, ticketing, source-control systems, backups and approved vendor services.

It applies to structured and unstructured data. It covers both personal and non-personal business records where a retention period is listed.

It does not override a litigation hold, regulatory preservation notice, active security investigation or contractual obligation requiring a longer period. A hold pauses ordinary deletion for the records in scope.

## Roles

The **data owner** decides why a record is needed and confirms the appropriate schedule category. **System owners** configure deletion or archive controls where technically feasible. **Security** owns logging and incident holds. **People Operations** owns HR and recruitment records. **Finance** owns accounting, expense and supplier-payment records. **Customer Success** owns support-case records. **Legal/Commercial Operations** owns executed contracts and formal legal holds.

Employees must not create private archives to evade a retention rule.

## Classification and retention

Information classification and retention are different concepts. A record can be Public and still have a retention rule, or Confidential and have a short retention rule. Classification controls who may access the record; retention controls how long it should remain.

Northline uses Public, Internal and Confidential classifications under `NL-SEC-AUP-2026`.

## Master retention schedule

| Record type | Standard retention | Trigger | Owner | Disposal method |
|---|---:|---|---|---|
| Customer support tickets | 24 months | Ticket closure | Customer Success | Delete/anonymise in ticket platform |
| Recorded support calls | 90 days | Recording date | Customer Success | Automatic deletion |
| Customer contracts/order forms | 7 years | Contract end | Commercial Ops | Secure deletion after hold check |
| Supplier/vendor contracts | 7 years | Contract end | Finance/Procurement | Secure deletion after hold check |
| Unsuccessful candidate CVs | 12 months | Hiring decision | People Ops | Delete from ATS |
| Candidate interview notes | 12 months | Hiring decision | People Ops | Delete from ATS/approved folder |
| Employee personnel file | 7 years | Employment end | People Ops | Secure deletion |
| Payroll summaries and approvals | 7 years | End of financial year | Finance/People Ops | Secure deletion |
| Expense claims and receipts | 7 years | End of financial year | Finance | Secure deletion |
| Supplier invoices | 7 years | End of financial year | Finance | Secure deletion |
| Security authentication logs | 12 months | Event date | Security | Rolling deletion |
| Endpoint-security logs | 12 months | Event date | Security | Rolling deletion |
| Incident records Sev1/Sev2 | 5 years | Incident closure | Security/Ops | Secure deletion after hold check |
| Incident records Sev3 | 24 months | Incident closure | Operations | Secure deletion |
| Product telemetry linked to user/customer | 13 months | Event date | Engineering | Rolling deletion/anonymisation |
| Aggregated non-identifiable analytics | 36 months | Aggregation date | Product | Delete or refresh |
| Customer account data after termination | 90 days | Service termination | Engineering | Delete/anonymise unless contract says otherwise |
| Sales prospect records with no active opportunity | 24 months | Last meaningful interaction | Sales Ops | Delete or suppress |
| Marketing unsubscribe/suppression record | 6 years | Opt-out date | Marketing Ops | Retain minimal suppression proof |
| Routine internal chat | 24 months | Message date | IT | Rolling deletion |
| Routine employee email | 36 months | Message date | IT | Rolling deletion unless held |
| Board minutes and signed resolutions | Permanent | Approval date | Company Secretariat | Preserve |
| Corporate formation and share records | Permanent | Creation | Company Secretariat | Preserve |
| Vendor due-diligence file, approved vendor | Contract term + 7 years | Contract end | Procurement | Secure deletion |
| Vendor due-diligence file, rejected vendor | 12 months | Rejection | Procurement | Secure deletion |
| Visitor/access logs | 90 days | Visit/access date | Facilities/Security | Rolling deletion |
| CCTV where used | 30 days | Recording date | Facilities/Security | Rolling deletion unless incident hold |
| Backup copies | 35 days | Backup creation | IT | Rolling expiry |
| Deletion/audit logs proving disposal | 24 months | Disposal event | Security/IT | Rolling deletion |

The table is the authoritative default schedule. Prose examples in this document must be read consistently with the table.

## Customer support data

Support tickets are kept for **24 months after closure**. The period supports trend analysis, repeat-issue investigation, customer-history continuity and quality review without making the ticketing platform a permanent archive.

Agents should not place unnecessary credentials, identity documents or sensitive personal data in a ticket merely because the ticket itself has a 24-month period. Unneeded sensitive attachments should be removed earlier where feasible and documented.

Recorded support calls have a shorter period of **90 days from recording**. A call needed for a complaint, incident or contractual dispute may be placed on a hold before the automatic deletion date.

A Jira bug linked from a ticket follows the record category applicable to the Jira project rather than inheriting the ticket's 24-month period automatically. Customer-specific personal data should be minimised in Jira.

## Customer account and product data

When a customer terminates service, Northline's default is to retain customer account data for **90 days after service termination** to support documented export, restoration or close-out needs, then delete or anonymise it unless the contract requires a different period.

Routine product telemetry that can still be linked to a user or identifiable customer is retained for **13 months from event date**. After that period it should be deleted or transformed into genuinely non-identifiable aggregate statistics where the analytics purpose remains valid.

The 13-month period does not apply to an event that has been copied into a security incident file. The incident file then follows the incident retention rule.

## Contracts

Executed customer and supplier contracts, order forms, statements of work, material amendments and termination notices are retained for **7 years after the contract ends**.

Drafts that have no continuing business value should be deleted once the final agreement is signed or the negotiation is abandoned, normally within 12 months. A materially negotiated draft that helps explain a live dispute may be retained with the contract file until the dispute is resolved and any hold is released.

Only the approved contract repository is the record copy. Email copies do not need to be preserved solely because a final signed agreement exists in the repository.

## Recruitment records

For an unsuccessful candidate, Northline retains the CV, application and interview notes for **12 months after the hiring decision**. Recruiters should not keep a separate desktop or inbox archive beyond that period.

If a candidate expressly joins a talent community for future roles, the ATS may retain the profile under a separately documented purpose and notice. The existence of a talent-community record does not justify retaining every interview note indefinitely.

Successful candidate records that become part of the employee file follow the employee record schedule rather than the unsuccessful-candidate 12-month rule.

## Employee records

The core employee personnel file is retained for **7 years after employment ends**. It includes signed employment documents, material compensation changes, formal performance records, disciplinary outcomes and key leave/pay records where People Operations identifies them as part of the employment record.

Routine working notes that have served their purpose should not be moved into the permanent personnel file simply to avoid deletion. Managers should delete duplicate local copies once the official record is stored.

Medical and accommodation records are Confidential and should be segregated within the HR system so that access is limited to staff with a genuine People Operations need.

## Finance records

Expense claims, receipts, supplier invoices, payment approvals and payroll summaries are retained for **7 years after the end of the financial year to which the record primarily relates**. Finance should use the accounting system or approved archive as the record copy.

A routine Slack message saying “approved” is not the record copy if the approval is already captured in the expense or procurement system.

## Security logs

Authentication, identity-provider, firewall, endpoint and similar routine security logs are retained for **12 months from event date** unless a system has a documented shorter technical period approved by Security or the log is preserved for an active incident.

Security may place relevant logs on an incident hold. Copies preserved into a Sev1 or Sev2 incident file are then retained for **5 years after incident closure**. Sev3 incident records are retained for **24 months after closure**.

Security logs should not be retained permanently merely because storage is inexpensive.

## Email and chat

Routine internal chat is retained for **24 months**. Routine employee email is retained for **36 months**. These periods are defaults for messages that are not the official record of another category.

Employees are expected to move executed contracts, formal HR records, material approvals and other records of continuing value into the designated system rather than rely on a mailbox or chat history as the archive.

A hold can suspend deletion for specific custodians, channels, terms or date ranges.

## Backups

Northline uses rolling backups with a standard retention of **35 days**. Backups are for recovery, not long-term records management.

When a source record reaches its deletion date, Northline is not required to surgically remove the record from every immutable backup immediately if doing so is technically impractical. The record should disappear as the backup set ages out within 35 days, and restored data must be subject to the same deletion rules after recovery.

Backup access is restricted to authorised IT and Security personnel.

## Legal and investigation holds

A hold overrides normal deletion for records within its scope. Holds may arise from litigation, a regulatory request, a serious complaint, an insurance matter, a security incident or another formally documented need.

The hold notice should identify the owner, scope, custodians or systems, start date and release authority. Employees receiving a hold instruction must not delete, alter or conceal covered records.

When the hold is released, ordinary retention resumes. If the normal retention date passed during the hold, covered records should be deleted within a reasonable operational window after release unless another purpose now applies.

## Data subject requests and deletion requests

A request from an individual to delete personal data does not automatically override every retention rule. The privacy team must assess the request against the purpose, applicable law, contractual needs, legal claims and other rights or obligations.

Operational staff should not promise deletion before that review. They should route the request through the privacy process.

## Disposal methods

For cloud systems, disposal means deletion through the application's approved administrative process or API, followed by ordinary provider backup expiry. For managed endpoints, disposal means secure device wipe or approved destruction. Paper records containing Confidential information must use secure shredding.

Where full deletion is not required but analytics value remains, data may be anonymised only if the result is not reasonably linkable back to an individual or customer under Northline's intended use.

## Exceptions

A team that needs a different retention period must document:

- the record category;
- proposed period and trigger;
- business or legal reason;
- system and owner;
- privacy/security impact;
- whether data can instead be aggregated or minimised.

The data owner and Security or Privacy must approve the exception. Finance and People Operations must approve exceptions affecting their record categories.

An exception should have a review date. “Keep forever” is not an acceptable reason by itself.

## System implementation

System owners should automate retention where practical. If a system cannot enforce the schedule, the owner must use a documented manual review or export-and-delete process at least annually.

A new SaaS tool that will store Confidential data should be checked for configurable retention, export and deletion capability during vendor onboarding under `NL-PROC-VENDOR-2026`.

## EU and UK processing

Northline's Manchester operations are subject to the UK data-protection framework for relevant processing; Amsterdam processing may fall under EU GDPR and Dutch supervisory arrangements.

This policy deliberately sets operational periods rather than trying to turn the GDPR into a universal retention table. The appropriate period depends on purpose, legal obligations, claims and data minimisation. That is why some Northline records are held for days or months while contracts and core finance records are held for years.

## US records

US records may be subject to separate contractual, employment, tax, security or litigation requirements. The group schedule is the default unless the US record owner documents a longer requirement. A local requirement does not automatically extend the same record category globally.

## Retention inventory and system mapping

Security maintains a lightweight retention inventory showing the main system, record categories, system owner, configured deletion rule and any approved exception. The inventory does not need to list every database column; it should be detailed enough to show where the master schedule is implemented.

When a team introduces a new system, the owner should map each significant data set to an existing record category before go-live. If a system contains several categories, the team may need separate workspaces, tables or deletion rules. A single “keep everything seven years” setting is not acceptable merely because one finance record in the system has a seven-year period.

## Retention examples

### Closed support ticket with a linked contract dispute

A normal support ticket closes on 10 February 2026 and would ordinarily be deleted 24 months later. If Legal/Commercial Operations places the ticket on a dispute hold before that date, deletion pauses. When the hold is released, the ticket can be deleted if its ordinary 24-month period has already expired and no new purpose applies.

### Candidate considered for two roles

A candidate applies for one role, is declined, and is then considered for another role two months later with the candidate's knowledge. The 12-month period for the active recruitment file may be measured from the final hiring decision for that later process. Recruiters should not keep unrelated interview notes from older roles merely because the candidate remains in a talent community.

### Contract renewal

A three-year customer contract is renewed for a further two-year term. The record copy of the original contract, renewal and amendments is retained as one contract history until seven years after the final contractual relationship ends, unless a hold or different signed obligation requires longer.

### Security event copied into an incident case

An authentication event would ordinarily roll off after 12 months. If the same log extract becomes evidence in a Sev1 incident, the preserved incident copy follows the five-year Sev1/Sev2 incident-record period. The source logging platform does not need to retain every unrelated authentication event for five years.

### Customer termination and backups

A terminated customer's account data reaches the 90-day deletion point. The production copy is deleted or anonymised then. A copy may remain in immutable rolling backups until those backups expire, normally within the 35-day backup window. If a disaster recovery restore reintroduces the deleted data, the recovery runbook must reapply deletion.

## Data minimisation during retention

A retention period is not permission to collect extra data. A support ticket retained for 24 months should contain only the information needed to support the customer and investigate the case. A vendor file retained for years should not contain personal identification documents unless there was a genuine need to collect them.

Teams should prefer stable identifiers over unnecessary copies of personal data. For example, an incident record can link to a controlled HR case rather than reproducing a medical detail in an engineering ticket.

## Deletion verification

For high-risk systems, the system owner should test deletion at least annually. A test may use a non-production or synthetic record to confirm that the configured rule actually removes or anonymises data. The owner records the date, result and any remediation ticket.

A dashboard showing a retention setting is not sufficient evidence where the system is known to have archive, export or secondary-index behaviour that could defeat deletion. Owners should understand the main copies under Northline's control.

## Vendor-hosted data

Where a SaaS vendor stores Northline records, the Northline system owner remains responsible for mapping the vendor's settings to this policy. Vendor statements such as “data may be retained for service improvement” must be reviewed where they conflict with a Northline deletion requirement or approved processing terms.

At offboarding, the owner should disable access, request deletion or return where appropriate, and keep evidence of the request in the vendor file. The vendor file itself then follows its separate retention rule.

## Archives and exports

Bulk exports create new copies and therefore new deletion risk. Exports of Confidential information should have a named purpose and owner. Temporary exports used for migration, analysis or incident work should be deleted when the task is complete, normally within 30 days unless the underlying record schedule or hold requires longer.

Personal “archive” folders are not approved retention systems. If a user believes a record needs longer preservation, they should move it into the designated repository under the correct category or request an exception.

## Mergers, acquisitions and organisational change

If Northline acquires a business or migrates records between entities, the receiving owner should map inherited data to this schedule or document a temporary transition schedule. Migration is not a reason to reset every retention clock to day one. Where the original trigger date is known, preserve it.

If an office closes or a system is retired, records of continuing value should move to the approved successor repository and obsolete copies should be deleted after validation.

## Policy breaches

Accidental over-retention should be reported to the system owner and Security/Privacy so the team can correct the configuration and assess impact. Deliberate creation of hidden archives or deletion of records subject to a known hold may be handled under `NL-HR-CODE-2026`.

The preferred response to an ordinary retention defect is to fix the system and prevent recurrence, not to conceal the backlog.

## Annual review

Security and Privacy review the schedule annually with People Operations, Finance, Customer Success, Engineering and Commercial Operations. The review should check whether systems actually delete on schedule, not only whether policy text exists.

Material changes are recorded in `NL-POLICY-CHANGELOG-2026`.

## Appendix: retention decision worksheet

Use this worksheet when a new record type is not clearly covered above.

### Identify the record

Record name:  
System:  
Business owner:  
Contains personal data: yes/no  
Classification: Public/Internal/Confidential

### Define the purpose

State the purpose in one or two sentences. Avoid vague answers such as “might be useful”.

### Choose a trigger

A retention period needs a start or end trigger. Common triggers are creation date, ticket closure, contract end, employment end, hiring decision, financial-year end or incident closure.

### Test the proposed period

Ask whether the proposed period is needed for the stated purpose, whether a shorter period would work, whether records are duplicated elsewhere, whether the data can be anonymised, and whether a legal hold process already covers exceptional preservation.

### Approval

The data owner proposes the period. Security/Privacy reviews it. Finance or People Operations also approves where their domain is affected. The final period should be added to this schedule or to a controlled system-specific schedule that references this policy.

## Ownership

Policy owner: Head of Security. Privacy lead: Data Protection Lead. System owners are accountable for implementing approved schedules in their systems.
