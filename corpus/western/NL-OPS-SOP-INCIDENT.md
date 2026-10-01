SYNTHETIC

---
id: NL-OPS-SOP-INCIDENT
title: Production Incident Response SOP
doc_type: sop
jurisdiction: group
classification: Confidential
effective: 2026-03-01
supersedes: NL-OPS-SOP-INCIDENT-2025
synthetic: true
---

# Production Incident Response SOP

## Executive summary

Northline uses **Sev1, Sev2 and Sev3** for operational incidents. Sev1 is a critical outage, serious security event or material data-integrity event; Sev2 is major degradation with limited scope or a workable mitigation; Sev3 is a lower-impact operational defect.

Internal acknowledgement targets are **10 minutes for Sev1**, **30 minutes for Sev2** and **1 business day for Sev3**. Sev1 customer/status updates are normally every **30 minutes** while material impact continues; Sev2 updates are every **2 hours** during active handling.

## Severity table

| Severity | Example | Internal acknowledgement | Update cadence |
|---|---|---:|---:|
| Sev1 | broad production outage; confirmed material data corruption; active serious compromise | 10 min | 30 min |
| Sev2 | major feature unavailable for subset of customers; degraded performance with workaround | 30 min | 2 hours |
| Sev3 | minor defect, isolated failure, low-risk internal service issue | 1 business day | daily or on material change |

## Immediate steps

1. Open the incident channel and incident record.
2. Assign an Incident Commander (IC).
3. Name a technical lead and communications owner.
4. Record start time, detected time, affected services and known customer impact.
5. Stabilise the service before pursuing a perfect root-cause theory.
6. Link all related support tickets and Jira issues.
7. For suspected security incidents, add Security immediately and restrict sensitive detail to approved channels.

## Communications tree

**Detector → on-call engineer → Incident Commander → Security/Support/Engineering as needed → executive duty contact for Sev1.**

Customer Support owns individual case updates. The communications owner controls status-page wording. Engineering should not publish independent customer-facing root-cause statements during an active incident.

## Jira requirement

Every Sev1 and Sev2 incident requires a Jira incident or problem ticket. Sev3 requires Jira when Engineering work is needed or the issue is a reproducible product defect.

## Resolution

The IC may declare mitigation when customer impact is materially reduced and recovery is stable. “Resolved” means the service is restored and immediate risk is controlled; it does not require the final root-cause analysis to be complete.

## Post-incident review

A Sev1 review is due within **5 working days**. A Sev2 review is due within **10 working days** where the incident exposed a material process or technical weakness. Track corrective actions with owners and due dates.

Incident records are retained under `NL-SEC-DATA-RETENTION-2026`: Sev1/Sev2 records for 5 years after closure and Sev3 records for 24 months.
