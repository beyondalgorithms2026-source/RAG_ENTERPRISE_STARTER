SYNTHETIC

---
id: NL-FIN-SAMPLE-INVOICE-GUIDE
title: Supplier Invoice Recognition Guide
doc_type: sop
jurisdiction: group
classification: Internal
effective: 2026-04-01
supersedes: none
synthetic: true
---

# Supplier Invoice Recognition Guide

## Purpose

This is a retrieval guide for staff reviewing supplier invoices. It is not an invoice-extraction specification and does not teach jurisdiction-specific tax calculation.

A valid-looking supplier invoice should normally show the supplier's legal identity, the invoice identity, what was supplied and enough commercial detail for Finance to match it to an approved vendor or purchase.

## Expected fields

| Field | What staff should recognise |
|---|---|
| Supplier legal name | Legal entity issuing the invoice |
| Supplier address | Business or registered/remit-to address |
| Invoice number | Unique invoice reference |
| Invoice date | Date invoice was issued |
| Purchase order | Northline PO number where a PO was issued |
| Bill-to customer | Northline entity or office being billed |
| Line items | Description, quantity or period, unit price where relevant |
| Subtotal | Amount before tax and adjustments |
| Tax | Generic VAT or sales-tax line where applicable |
| Total due | Final invoice amount and currency |
| Payment terms | Due date or agreed terms |

## Basic checks

The supplier name should match the onboarded vendor or an approved legal-name change. The invoice number should not duplicate a previously paid invoice from the same supplier. A PO, where required, should match the relevant business owner and expected amount.

A bank-detail change shown only on an invoice is not enough to update vendor payment instructions. Follow `NL-PROC-VENDOR-2026` and independently verify the change.

## Red flags

Escalate an invoice that has an unexplained bank-account change, altered-looking payment instructions, an unknown supplier, a mismatched legal entity, duplicated invoice number, vague high-value line item, or a request to bypass the normal approval route.

Do not invent missing fields on the supplier's behalf. Ask Finance or the vendor for a corrected invoice.
