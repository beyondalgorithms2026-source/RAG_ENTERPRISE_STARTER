SYNTHETIC

---
id: NL-CORPUS-NOTES-2026
title: Northline Synthetic Corpus Consistency Notes
doc_type: appendix
jurisdiction: group
classification: Internal
effective: 2026-06-01
supersedes: none
synthetic: true
---

# Corpus Notes

## Purpose

These notes define the cross-document facts that should remain stable when the corpus is used for RAG retrieval and evaluation. They are not a separate employee policy.

## Company assumptions

Northline Analytics Ltd is a synthetic UK-registered B2B SaaS company of about 80 people with offices in Manchester, Austin and Amsterdam. No real address, employee or customer is implied by this corpus.

The holiday year is **1 January to 31 December** in all offices.

## Leave consistency

UK full-time employees: **25 days annual leave + 8 bank holidays** on the England and Wales calendar.

Austin full-time employees: **20 days PTO + 10 Northline US company holidays**.

Amsterdam full-time employees: **25 days annual leave + local public holidays**.

UK annual-leave carry-over: **up to 5 days**, normally used by **31 March** of the following year.

UK company sick pay after probation: **20 working days at 100% salary in a rolling 12-month period**. During probation: **5 working days at 100%**.

UK enhanced maternity/adoption pay: weeks **1–16 at 100%**, weeks **17–26 at 50% or statutory if greater**, then statutory pay where eligible, then unpaid remainder of statutory leave. Enhanced paternity pay: **2 weeks at 100%**. Enhanced Shared Parental Leave: first **6 weeks taken by a Northline employee at 100%**, subject to policy eligibility. Neonatal Care Leave top-up: up to **4 weeks at 100%**. Austin company parental leave: **12 weeks at 100%** after 6 months' service.

## Expense consistency

Daily meal caps: **£65 UK / $85 US / €75 NL/EU**.

Hotel caps: **London £240 / Amsterdam €220 / Austin $220 / New York $300**. Other-city defaults: **£180 / $220 / €200**.

Receipt threshold for ordinary individual expenses: **£25 / $30 / €30**, with receipts always required for hotel, air, rail, rental car and client entertainment.

Finance pre-approval for a single planned purchase: **£1,000 / $1,250 / €1,150**.

Director + Finance pre-approval for an expected trip total: **£2,500 / $3,200 / €2,900**.

Client-entertainment escalation threshold: **£300 / $375 / €350 total per event**.

Mileage: **UK £0.45/mile first 10,000 business miles, then £0.25; US $0.67/mile; NL/EU €0.30/km**.

Home-office allowance: **£600 / $750 / €700 once every 36 months**.

## Retention consistency

Support tickets: **24 months after closure**. Recorded support calls: **90 days**. Customer and supplier contracts: **7 years after contract end**. Unsuccessful candidate CVs and interview notes: **12 months after hiring decision**. Employee personnel files: **7 years after employment end**. Finance records: **7 years after relevant financial-year end**. Security logs: **12 months**. Product telemetry linked to a user/customer: **13 months**. Customer account data after service termination: **90 days**. Routine chat: **24 months**. Routine email: **36 months**. Backups: **35 days**. Sev1/Sev2 incident records: **5 years after closure**. Sev3 records: **24 months after closure**.

## Support SLA consistency

Priority labels: **P1 Critical, P2 High, P3 Standard**.

Default first response: **P1 1 business hour / P2 4 business hours / P3 1 business day**.

UK support window: **09:00–17:30 Europe/London, Monday–Friday excluding UK bank holidays**.

US support window: **09:00–17:00 America/Chicago, Monday–Friday excluding Northline US company holidays**.

P1 support update target: **every 2 business hours** unless the incident SOP uses the faster Sev1 cadence. Incident cadence: Sev1 internal acknowledgement **10 minutes** with **30-minute** updates; Sev2 acknowledgement **30 minutes** with **2-hour** updates; Sev3 acknowledgement **1 business day**.

## Vendor consistency

Vendor high-risk spend threshold: above **£25,000 / $32,000 / €29,000 annual value**, while certain data/system-access conditions make a vendor high-risk regardless of spend.

US payee documentation: W-9 for relevant US persons; W-8BEN for relevant foreign individuals; W-8BEN-E or another applicable W-8 for foreign entities as Finance determines.

## Length-mix assumption

The request specifies 14 corpus documents but a page-length mix totalling 11 documents: 3 short + 6 medium + 2 long. The corpus therefore applies the mix to the 11 substantive policy/SOP/reference documents and treats `NL-CS-MACROS`, `NL-POLICY-CHANGELOG-2026` and `NL-TEST-POISON-DOC` as utility fixtures outside the page-count mix.

The intended long documents are `NL-HR-LEAVE-2026` and `NL-SEC-DATA-RETENTION-2026`. The intended medium documents are the main Expense, Support, AUP, Remote, Vendor and Code documents. The intended short documents are the Expense Rates Appendix, Incident SOP and Sample Invoice Guide.

## Deliberate quirks

The corpus includes: a policy with an appendix (`NL-FIN-EXPENSE-2026` plus the rates appendix); multiple 2026 documents that supersede synthetic 2025 identifiers; a Mermaid timeline in the changelog; and a poison-candidate sentence only in `NL-TEST-POISON-DOC`.

The scanned-style markdown table is in `NL-FIN-EXPENSE-APPENDIX-RATES`. Its compressed headings and spacing are deliberate while its values still match the operative expense policy.

## Research grounding

The synthetic UK leave structure was checked against current GOV.UK guidance on annual leave, maternity, paternity, shared parental leave, neonatal care and statutory sick pay.

The retention approach was checked against the GDPR storage-limitation framework and EU data-protection sources.

The US vendor-document wording was checked against IRS materials on Forms W-9 and W-8BEN/W-8BEN-E.
