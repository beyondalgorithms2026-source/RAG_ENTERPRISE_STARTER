SYNTHETIC

---
id: NL-PROC-VENDOR-2026
title: Vendor Onboarding and Contracting Procedure
doc_type: sop
jurisdiction: group
classification: Internal
effective: 2026-04-15
supersedes: NL-PROC-VENDOR-2025
synthetic: true
---

# Vendor Onboarding and Contracting Procedure

## Executive summary

No vendor may receive Northline Confidential data, connect to Northline systems or begin recurring paid work until the business owner completes onboarding at the level required by risk and spend.

US payees normally provide a **Form W-9** when they are US persons for whom Northline needs taxpayer identification information. Relevant non-US payees may instead be asked for an applicable IRS Form W-8; **Form W-8BEN is for foreign individuals and Form W-8BEN-E is generally used for foreign entities**.

UK corporate vendors should provide their legal company name, registered company number where applicable, billing address and bank/payment details through the approved Finance process. Vendors handling customer data or connecting to production require Security review regardless of spend.

## Roles

The **business owner** explains the need and confirms budget. **Finance** checks payment setup, duplicate vendors and commercial thresholds. **Security** reviews vendors that process Confidential data, integrate with company systems or present material operational risk. **Privacy** reviews personal-data processing where needed. **Commercial Operations** or the designated contract owner reviews contract terms. Only an authorised signatory may sign for Northline.

## Intake

Before asking a vendor to start work, the business owner submits:

- vendor legal name and trading name if different;
- country of formation and company number/registration identifier where applicable;
- business purpose and expected users;
- expected annual and first-year spend;
- whether the vendor will receive Public, Internal or Confidential data;
- whether the vendor connects to Northline systems;
- proposed start and renewal date;
- contract or online terms;
- named Northline budget owner.

Finance checks whether an approved vendor already provides the same capability.

## Risk tiers

### Low risk

A low-risk vendor has spend below **£5,000 / $6,500 / €5,800 per year**, receives no Confidential data, has no system integration and does not provide a business-critical service.

Low-risk onboarding requires business-owner approval, Finance setup and acceptance of reasonable terms.

### Standard risk

A standard-risk vendor has annual spend from **£5,000 to £25,000 / $6,500 to $32,000 / €5,800 to €29,000**, or receives Internal information, or provides an operationally important service.

Standard-risk onboarding requires business owner, Finance and contract review. Security reviews it if there is data access or integration.

### High risk

A high-risk vendor includes any vendor that processes customer production data, hosts Confidential employee data, connects to production, provides identity/security infrastructure, is critical to service availability, or has annual spend above **£25,000 / $32,000 / €29,000**.

High-risk onboarding requires business owner, Finance, Security, appropriate privacy review and Commercial Operations. A data-processing agreement or security schedule is required where applicable.

## Payee and company information

### US payees

For US payment setup, Finance requests the appropriate taxpayer documentation. A US person commonly provides Form W-9. A foreign individual may be asked for Form W-8BEN, and a foreign entity may require Form W-8BEN-E or another appropriate W-8 form depending on status and payment type. Finance, not the business owner, decides which form is required.

Staff must not “correct” a tax form for the vendor. An incomplete form is returned to the vendor or Finance adviser for resolution.

### UK vendors

For a UK incorporated vendor, collect legal company name, registered company number, billing address, remit-to details and the contact authorised to discuss payment. Finance should verify that invoice details reasonably match onboarding records before the first payment.

### Netherlands and other EU vendors

Collect the vendor's legal entity name, local registration identifier, billing address, payment details and any invoicing information Finance requests. Tax should be shown only as a generic VAT or sales-tax line in Northline's retrieval corpus; this procedure does not attempt to teach jurisdiction-specific tax calculation.

## Insurance

A vendor performing onsite work, professional services or services that could cause material loss may be required to evidence insurance.

Default expectations are:

| Vendor type | Expected insurance |
|---|---|
| General professional services | Professional liability / errors and omissions of at least £1m / $1m / €1m where commercially available |
| Vendor with production/data access | Cyber/privacy liability of at least £1m / $1m / €1m |
| Onsite physical work | General/public liability of at least £2m / $2m / €2m |

These are company procurement thresholds, not statements of law. Finance or Security may approve a lower limit for a small low-risk supplier if the risk is documented.

## Security review

Security review is mandatory when a vendor will:

- receive Confidential data;
- process customer data;
- connect to SSO, source control, ticketing, CRM, finance, HR or production systems;
- install an endpoint agent or browser extension;
- use AI models with Northline data;
- provide a critical hosting, identity, observability or backup function.

Security may request a security questionnaire, independent assurance report, penetration-test summary, architecture description, incident-notification terms, subprocessor list, data-location information and deletion/retention commitments.

## Privacy review

Privacy review is required where a vendor processes personal data on Northline's behalf or materially changes how personal data is used. The contract should cover processing instructions, confidentiality, security, subprocessors, deletion/return and incident support where appropriate.

The retention review should confirm that the vendor can support `NL-SEC-DATA-RETENTION-2026` or a documented system-specific exception.

## Contracting and signatures

No employee may sign a contract, click “accept” on paid business terms or bind Northline to auto-renewal unless authorised.

Signature authority for this synthetic corpus is:

| Contract value | Minimum Northline approval/signature |
|---|---|
| Up to £10,000 / $13,000 / €11,500 annual value | Department Director after Finance approval |
| Above £10,000 up to £50,000 / $13,000–$65,000 / €11,500–€58,000 | CFO or COO-equivalent role |
| Above £50,000 / $65,000 / €58,000 annual value | CEO or CFO plus functional director |
| Multi-year commitment above £100,000 / $130,000 / €115,000 total | CEO and CFO, with board notification |

Security or privacy risk can require additional approval regardless of spend.

## Purchase orders and invoicing

Where Finance issues a purchase order, the vendor should quote the PO number on invoices. Staff should use `NL-FIN-SAMPLE-INVOICE-GUIDE` to recognise required invoice fields.

A vendor must not be told to split invoices to avoid an approval limit.

## Bank-detail changes

A change to vendor bank details must be verified using a known contact method independent of the change request. Do not verify a bank-detail change by replying only to the email that requested it.

Finance records evidence of the verification.

## Renewal

The business owner reviews a recurring vendor at least **60 days before renewal** where notice periods permit. The review should confirm usage, business need, current spend, security changes, incidents, data retained, renewal uplift and whether a competitive alternative should be considered.

High-risk vendors receive a refreshed Security review at least every **24 months** or sooner after a material change or incident.

## Offboarding

When a vendor relationship ends, the business owner closes access, exports required records, confirms data return/deletion where applicable, disables integrations and tells Finance to stop future payment or auto-renewal.

The vendor file is retained under `NL-SEC-DATA-RETENTION-2026`: approved-vendor due-diligence records follow the contract term plus 7 years; rejected-vendor due diligence is retained 12 months after rejection.

## Exceptions

Urgent operational need does not remove the obligation to review risk. An emergency temporary purchase may be approved by the CFO and Head of Security for up to 30 days while full onboarding is completed.

## Ownership

Procedure owner: Finance/Procurement. Security owns security due diligence. Commercial Operations owns contract process. This procedure supersedes `NL-PROC-VENDOR-2025`.
