SYNTHETIC

---
id: NL-CS-SUPPORT-PLAYBOOK-2026
title: Customer Support Playbook
doc_type: playbook
jurisdiction: group
classification: Internal
effective: 2026-03-01
supersedes: NL-CS-SUPPORT-PLAYBOOK-2025
synthetic: true
---

# Customer Support Playbook

## Executive summary

Northline Customer Support uses three operational priorities: **P1 Critical**, **P2 High** and **P3 Standard**. Contract terms override this internal default, but where the customer order form is silent the target first-response times are **1 business hour for P1**, **4 business hours for P2** and **1 business day for P3**.

UK support hours are **09:00–17:30 Europe/London, Monday to Friday**, excluding UK bank holidays. US support hours are **09:00–17:00 America/Chicago, Monday to Friday**, excluding Northline US company holidays. An SLA clock runs only in the support window stated in the customer's contract; where a contract states “Northline business hours” without a region, the account's billing region controls.

All P1 issues, all reproducible product defects affecting more than one customer, and any issue requiring Engineering work must have a Jira ticket. Support must not promise a refund. Agents may acknowledge a refund request and route it for approval.

## Purpose and scope

This playbook covers inbound B2B SaaS support handled by Northline's UK and US support teams. It applies to email, portal and scheduled phone support. It does not create a contractual SLA by itself; signed customer terms control.

Support owns triage, customer communication, basic troubleshooting and case hygiene. Engineering owns code-level diagnosis and fixes. Customer Success owns adoption and account-health conversations. Finance approves billing credits and refunds unless a contract expressly delegates a small service credit to another role.

## Priority definitions

### P1 Critical

Use P1 when a production service is unavailable or materially unusable for the customer and there is no reasonable workaround, or when a security or data-integrity issue could cause significant customer impact.

Typical P1 examples include widespread login failure, production API outage, confirmed corruption of customer data, or a customer-specific outage blocking a time-critical production workflow.

Do not classify a request as P1 only because a customer is senior, angry or nearing renewal. Priority is based on impact and urgency.

### P2 High

Use P2 when important functionality is degraded, a key workflow is blocked but a workaround exists, multiple users are affected, or a defect is likely to cause material operational disruption without being a complete outage.

### P3 Standard

Use P3 for questions, how-to requests, minor defects, single-user issues with a workaround, feature requests, documentation questions, invoice-copy requests and ordinary configuration assistance.

## Default SLA targets

| Priority | First response | Update target while active | Typical owner |
|---|---:|---:|---|
| P1 Critical | 1 business hour | every 2 business hours, or incident cadence if faster | Support lead + incident commander |
| P2 High | 4 business hours | every 1 business day | assigned support engineer |
| P3 Standard | 1 business day | every 2 business days while active | assigned support engineer |

The first-response clock stops when a substantive human response is sent. An automated acknowledgement does not count as the first response. “Substantive” means the response confirms understanding of the issue and either gives a next step, asks a relevant diagnostic question, or states that escalation has begun.

The update target is an internal operating target, not a promise of resolution.

## Business-hour clocks

The UK queue runs from 09:00 to 17:30 Europe/London on working days. The US queue runs from 09:00 to 17:00 America/Chicago on working days. Public/company holidays pause the relevant clock.

If a UK-region P2 ticket arrives at 16:30 on a normal working day, one business hour elapses that day and the remaining three hours resume at 09:00 the next UK working day.

For customers with a documented follow-the-sun entitlement, the account record must explicitly say so; agents should not assume the UK and US windows automatically combine into a longer SLA window.

## Queue triage

The queue owner checks new cases at least every 30 minutes during business hours. For each case:

1. Confirm the customer and entitlement.
2. Read the full request and attachments.
3. Set P1, P2 or P3 based on impact.
4. Check for an existing incident, known issue or duplicate case.
5. Send or prepare the first substantive response.
6. Record product area, environment, affected users and reproduction status.
7. Create or link Jira where required.
8. Set the next-action date.

Cases must not remain unowned after triage.

## When to create a Jira ticket

Create a Jira issue when any of the following is true:

- the case is P1;
- a reproducible product defect affects more than one customer;
- a reproducible defect causes data loss, incorrect calculation or material workflow failure;
- Engineering investigation or code/configuration change is required;
- Support has performed the documented troubleshooting path and cannot resolve the issue;
- a defect has recurred after a prior fix;
- a security concern needs Security or Engineering investigation.

Do not create a bug for a feature request, a documentation-only request, known expected behaviour, a customer-specific configuration question resolved by Support, or a duplicate defect that already has an active Jira issue. Link the existing Jira instead.

A good Jira issue contains the customer-safe symptom, internal impact assessment, steps to reproduce, expected and actual behaviour, timestamps with time zone, environment, relevant logs or screenshots, and links back to affected support cases. Do not paste secrets, credentials or unnecessary customer personal data into Jira.

## Escalation model

### Support level one

Level 1 handles intake, entitlement check, known issues, password or access guidance, basic configuration, documentation and standard billing-document requests.

### Support level two

Level 2 handles deeper product troubleshooting, log review within approved tools, reproducible defect isolation, integration troubleshooting and coordination with Customer Success.

### Engineering and specialist escalation

Engineering is engaged through Jira and the designated escalation channel. Security concerns are routed to Security immediately. Billing disputes go to Finance. Contract interpretation goes to Customer Success plus the commercial owner.

For P1, follow `NL-OPS-SOP-INCIDENT`. The incident commander, not the support agent, controls incident status cadence once a formal incident is declared.

## Customer communication standards

Use plain language. State what is known, what is not yet known and what will happen next. Do not speculate about root cause before Engineering or the incident commander confirms it.

Avoid statements such as “this will definitely be fixed today” unless the responsible technical owner has committed to that plan and the support lead agrees it is safe to communicate.

For a known incident, link the case to the incident record and use the approved status text. Do not send different root-cause theories to different customers.

## Refunds, credits and goodwill

Support may acknowledge a request for refund or service credit but may not approve one unless a written delegation exists.

Approved language is:

> I understand why you're asking for a credit. I’ve recorded the request and routed it to the team that reviews commercial adjustments. I can’t confirm an amount or outcome from Support, but we’ll update you after the review.

A billing correction caused by a clear administrative error should be routed to Finance. A service-credit request tied to SLA performance should be routed to Customer Success and Finance with the relevant ticket and incident timestamps.

Do not use words such as “refund guaranteed,” “we owe you,” or “automatic credit” unless the signed customer terms clearly require that outcome and the commercial owner has confirmed it.

## SLA miss handling

If Support misses a first-response target, the agent should not hide or reset the timestamps. Send the approved apology macro from `NL-CS-MACROS`, provide the current next step and tag the case `sla_miss`.

The support lead reviews P1 and P2 SLA misses weekly for staffing, routing or process issues. A missed internal target does not automatically mean a contractual SLA was breached; compare the ticket against the customer's actual support terms.

## Feature requests

A feature request remains a P3 support case unless it is attached to a separate incident or defect. Capture the business problem, not only the requested solution. Route it to the product-feedback queue and tell the customer that submission does not create a delivery commitment.

Do not create Engineering Jira bugs merely to make a feature request visible. Use the product-feedback system unless Product specifically asks for a Jira discovery ticket.

## Security-sensitive tickets

If a customer reports suspected account compromise, exposed credentials, unexpected data access or another security concern, do not ask them to email secrets or full access tokens. Preserve the ticket, alert Security through the incident channel and follow `NL-OPS-SOP-INCIDENT` if impact may be Sev1 or Sev2.

Support may ask for token identifiers, timestamps, usernames or redacted request IDs where useful. Never request a password.

## Billing and invoice-copy requests

Support may provide an existing invoice copy after confirming the requester is an authorised billing contact or after routing through the customer's verified admin contact. Support must not alter supplier or customer tax details in a PDF. Requests to change legal billing details go to Finance.

## Password and access requests

Support should direct users to self-service reset where available. For admin-reset requests, verify the requester's authority using the account's approved verification path. Never set or email a temporary password in plain text if the product supports a secure reset link.

## Closing a case

A case may be closed when:

- the customer confirms resolution;
- Support has supplied the requested information and no further action is due;
- the underlying incident is resolved and the customer has been notified;
- repeated requests for required information receive no response for 10 business days after two follow-ups.

Before closing a defect-linked case, record the Jira link and fix version if known. Do not delay closure solely because a feature request has no roadmap date.

## Quality review

Support leads sample at least 10 closed cases per month across priorities. Review includes correct priority, useful first response, Jira hygiene, data handling, tone, next-action discipline and whether any commercial promise was made without authority.

## Metrics

The team tracks first-response attainment, median first response, reopen rate, backlog age, P1 count, P2 count, customer satisfaction where available and Jira escalation rate. Metrics are used to find process problems, not to encourage agents to lower priority improperly.

## Ownership and review

Owner: Director of Customer Success. Operational owner: Support Lead. Incident process owner: Operations. Security-sensitive handling is jointly owned with Security.
