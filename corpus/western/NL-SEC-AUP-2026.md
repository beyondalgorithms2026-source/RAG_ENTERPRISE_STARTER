SYNTHETIC

---
id: NL-SEC-AUP-2026
title: Acceptable Use, Devices and AI Tools Policy
doc_type: policy
jurisdiction: group
classification: Internal
effective: 2026-05-15
supersedes: NL-SEC-AUP-2025
synthetic: true
---

# Acceptable Use, Devices and AI Tools Policy

## Executive summary

Northline systems are for authorised business use. Company-managed devices must use full-disk encryption, screen lock, supported security software and **multi-factor authentication (MFA)** for company accounts where available. Staff must not disable endpoint controls or share credentials.

Northline uses three information classifications: **Public**, **Internal** and **Confidential**. Confidential data must not be pasted into consumer or unapproved AI tools. Public generative-AI services such as ChatGPT or Claude may be used only with Public information unless Northline Security has approved the specific enterprise service and data use. “Shadow AI” accounts purchased or connected without approval are prohibited for company data.

## Scope

This policy applies to employees, contractors and temporary staff who use Northline systems, devices, networks or data. It covers laptops, mobile devices, cloud services, SaaS applications, source repositories, customer systems and AI assistants.

## Information classification

### Public

Public information is approved for unrestricted external release. Examples include published website content, approved press material, public job postings and public product documentation.

### Internal

Internal information is intended for Northline personnel and approved service providers with a business need. Examples include routine internal procedures, non-public project plans, internal meeting notes and ordinary operational metrics.

### Confidential

Confidential information could cause material harm if disclosed or misused. Examples include customer data, personal data, credentials, security findings, source code, non-public financial information, contracts, unreleased product strategy, HR records and incident evidence.

When unsure, treat information as Confidential until the owner or Security confirms otherwise.

## Accounts and authentication

Each user must use their own account. Shared accounts are allowed only where technically necessary and explicitly approved, with credentials stored in the approved password manager.

MFA is required for Northline email, identity provider, code hosting, production administration, finance systems, HR systems and other services designated by Security. Users must not approve an MFA prompt they did not initiate.

Passwords or recovery codes must not be stored in chat messages, tickets, source code or unencrypted documents.

## Devices

Northline laptops must remain enrolled in device management. Users must not disable disk encryption, endpoint detection, automatic security updates or screen-lock controls.

Company devices should be locked when unattended. Lost or stolen devices must be reported to Security as soon as noticed, even if the device appears encrypted.

Personal devices may access Northline email or collaboration tools only where mobile-device controls or another approved access method is in place. Production administration from an unmanaged personal computer is prohibited.

## Software and browser extensions

Users may install ordinary productivity software from approved sources where local device policy permits it. Tools that capture keystrokes, inspect browser content, record meetings, synchronise files externally or require broad administrator permissions need Security approval.

Pirated software, unlicensed commercial software, credential-sharing tools, cryptominers and unauthorised remote-access agents are prohibited.

## Generative AI and shadow AI

Generative AI can be useful for drafting, summarisation, code assistance and analysis, but external services may retain prompts or use them under terms that Northline has not reviewed.

The following rules apply:

| Data or activity | Consumer/public AI account | Security-approved enterprise AI service |
|---|---|---|
| Public information | Allowed | Allowed |
| Internal information | Not allowed unless Security has approved that exact service/use | Allowed where business owner approves use |
| Confidential information | Prohibited | Allowed only where the approved service and use case explicitly permit it |
| Credentials, secrets or private keys | Prohibited | Prohibited |
| Customer production data | Prohibited | Only with explicit Security and data-owner approval |
| Source code | Prohibited unless repository/project owner and Security approve | Allowed only for repositories covered by the approved configuration |

Examples of public AI tools include consumer ChatGPT, Claude and similar browser or mobile services. Naming a product here does not mean it is approved.

A user must not purchase an AI subscription, connect an AI plug-in to Google Workspace, source control, CRM, ticketing or file storage, or upload company datasets to a new AI platform without approval. This is “shadow AI” and is prohibited because the company may not have reviewed access scope, retention, training use or contractual terms.

AI output must be reviewed by a human before it is sent to customers, committed to production or used for a material business decision. AI-generated code must go through the normal code-review and security process.

## Email, messaging and collaboration

Users should use Northline-approved communication tools for company work. Confidential material should not be forwarded to personal email or personal messaging accounts.

Do not use collaboration tools to harass, threaten, discriminate, distribute unlawful material or conduct outside commercial activity that conflicts with Northline duties.

## Customer and production access

Access to production must be least-privilege and role-based. Users must not browse customer records out of curiosity or use production data for demos unless the data owner has approved the use and privacy requirements are met.

Production credentials must be stored in the approved secret-management system. Copying secrets to local notes or chat is prohibited.

## Removable media and file transfer

USB storage is blocked by default on managed endpoints where technically feasible. Security may approve encrypted removable media for a defined need.

Confidential files must be shared using approved Northline storage and access controls. Public file-transfer websites and personal cloud drives are not approved for company information.

## Security incidents

Immediately report suspected phishing, credential compromise, malware, lost devices, accidental external sharing, unusual MFA prompts or suspected customer-data exposure. Do not delay reporting while trying to prove whether an incident is real.

Follow `NL-OPS-SOP-INCIDENT` for severity handling.

## Monitoring and privacy

Northline may log and monitor use of company systems for security, reliability, compliance and business operations, subject to applicable law and internal privacy controls. Users should not expect personal privacy for activity conducted on company-managed systems beyond what local law and company notices provide.

Monitoring data is itself controlled and retained under `NL-SEC-DATA-RETENTION-2026`.

## Prohibited use

Northline systems must not be used to conduct unlawful activity, bypass access controls, run unauthorised security testing, intentionally introduce malicious code, operate a personal commercial service, mine cryptocurrency, distribute discriminatory or harassing content, or copy data beyond a legitimate work purpose.

Security research against Northline systems requires written authorisation and a defined test scope.

## Exceptions

Security may approve a time-limited exception where the business need is documented and compensating controls are reasonable. Exceptions must record owner, scope, expiry date and residual risk.

## Enforcement

Access may be suspended immediately where Security believes there is an active risk. Deliberate or repeated violations may be handled under `NL-HR-CODE-2026` and the employee's local employment process.

## Ownership and review

Owner: Head of Security. This policy supersedes `NL-SEC-AUP-2025` from 15 May 2026.
