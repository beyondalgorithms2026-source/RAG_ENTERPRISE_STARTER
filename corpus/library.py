"""The synthetic demo corpus, as data.

Everything here is invented. "Northwind Logistics" is a fictional European
freight and warehousing company. No real company, person, policy or document is
represented, and nothing here is confidential.

Documents are data rather than generated prose so that a reader can see exactly
what the system was asked about. `classification` and `owner_group` are not
decoration: the seed pack turns them into real ACL grants, so access control is
defined alongside the documents rather than configured separately and drifting.

EVAL_QUESTIONS lives in this file, next to the documents it refers to, for the
same reason. When the question set and the corpus are maintained apart they
drift, and drift is how a validator ends up knowing answers it should not.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    slug: str
    title: str
    classification: str  # public | internal | restricted
    owner_group: str
    body: str

    def filename(self) -> str:
        return f"{self.slug}.md"

    def render(self) -> str:
        return f"# {self.title}\n\n{self.body.strip()}\n"


@dataclass(frozen=True)
class EvalQuestion:
    """One eval case.

    `expected_document` is None for questions the corpus deliberately cannot
    answer. Those are the important ones: they test whether the system admits
    ignorance rather than inventing something plausible.
    """

    question: str
    expected_document: str | None
    expected_fact: str | None = None


COMPANY = "Northwind Logistics"


DOCUMENTS: list[Document] = [
    Document(
        slug="travel-expense-policy",
        title="Travel and Expense Policy",
        classification="public",
        owner_group="finance",
        body="""
## Scope

This policy applies to all Northwind Logistics employees travelling on company business.

## Booking

Domestic flights must be booked at least fourteen days in advance where the itinerary is
known. Economy class is the standard for all flights under six hours. Flights of six
hours or more may be booked in premium economy with written approval from a department
head.

## Daily allowance

The daily meal allowance is 45 EUR for domestic travel and 65 EUR for international
travel. Receipts are required for any single expense above 25 EUR.

## Accommodation

Hotel spend should not exceed 180 EUR per night in listed cities and 120 EUR per night
elsewhere. Where a conference venue rate exceeds these limits, the venue rate applies.

## Submitting a claim

Claims must be submitted within 30 days of the final day of travel. Claims submitted
after 60 days require director approval and may be refused.
""",
    ),
    Document(
        slug="remote-working-policy",
        title="Remote and Hybrid Working Policy",
        classification="public",
        owner_group="people-operations",
        body="""
## Eligibility

All Northwind Logistics employees whose role does not require physical presence at a
depot are eligible for hybrid working. Depot operations roles are excluded because the
work cannot be performed remotely.

## Expected office attendance

Hybrid employees attend the office a minimum of two days per week. Teams may agree a
fixed anchor day; where they do, attendance on that day takes precedence over the
individual minimum.

## Equipment

The company provides a laptop and one external monitor. A contribution of up to 250 EUR
towards a desk chair is available once every three years on production of a receipt.

## Working from another country

Working from outside your country of employment requires prior written approval and is
limited to 20 working days per calendar year, for tax residency reasons.
""",
    ),
    Document(
        slug="information-security-standard",
        title="Information Security Standard",
        classification="internal",
        owner_group="security",
        body="""
## Access control

Access to systems is granted on the principle of least privilege. Access is reviewed
quarterly. Accounts belonging to leavers are disabled on the final working day and
deleted after 30 days.

## Data classification

Documents are classified as public, internal, or restricted. Restricted documents may
only be accessed by members of the owning group and may not be forwarded outside the
company under any circumstances.

## Passwords and authentication

Multi-factor authentication is mandatory for all systems holding customer data. Shared
accounts are prohibited.

## Incident reporting

Suspected incidents must be reported to the security team within one hour of discovery.
Do not attempt to investigate a suspected compromise yourself.
""",
    ),
    Document(
        slug="compensation-bands-2026",
        title="Compensation Bands 2026",
        classification="restricted",
        owner_group="people-operations",
        body="""
## Purpose

This document records the approved salary bands for the 2026 review cycle. It is
restricted to People Operations and the executive team. It must not be shared with line
managers outside the review process.

## Bands

Band 3 (Associate): 38,000 to 47,000 EUR.
Band 4 (Professional): 46,000 to 61,000 EUR.
Band 5 (Senior): 60,000 to 79,000 EUR.
Band 6 (Lead): 76,000 to 98,000 EUR.

Bands overlap deliberately so that progression does not require a title change.

## Off-band offers

Any offer above the top of a band requires written approval from the Chief People Officer
and a documented market justification.
""",
    ),
    Document(
        slug="grievance-procedure",
        title="Grievance Procedure",
        classification="internal",
        owner_group="people-operations",
        body="""
## Raising a grievance

An employee may raise a grievance informally with their line manager, or formally in
writing to People Operations. Where the grievance concerns the line manager, it should be
raised directly with People Operations.

## Timescales

A formal grievance is acknowledged within five working days. A hearing is normally held
within fifteen working days of acknowledgement.

## Right to be accompanied

An employee may be accompanied at any formal hearing by a colleague or a trade union
representative.

## Appeals

An employee may appeal the outcome within ten working days of receiving it. The appeal is
heard by someone not involved in the original decision.
""",
    ),
    Document(
        slug="annual-leave-policy",
        title="Annual Leave Policy",
        classification="public",
        owner_group="people-operations",
        body="""
## Entitlement

Full-time employees receive 26 days of annual leave per calendar year, in addition to
public holidays observed in their country of employment. Part-time entitlement is
calculated pro rata.

## Booking

Leave must be requested through the leave system and approved by the line manager before
travel is booked. Requests of five consecutive days or more should be submitted at least
three weeks in advance.

## Carry-over

A maximum of five days may be carried into the following year and must be used by 31
March. Days not used by that date are forfeited.

## Depot coverage

Depot teams operate a coverage roster. No more than one third of a depot shift team may
be on leave on the same day, and requests are approved in the order received.

## Leaving the company

On leaving, accrued but untaken leave is paid in the final salary payment. Leave taken in
excess of accrual is deducted from the final payment.
""",
    ),
    Document(
        slug="sickness-absence-policy",
        title="Sickness Absence Policy",
        classification="public",
        owner_group="people-operations",
        body="""
## Reporting an absence

An employee unable to attend work must notify their line manager before the start of
their shift, or as early as possible where that is not practical. Notification by message
to a colleague is not sufficient.

## Certification

Absence of up to seven consecutive calendar days may be self-certified on return. Absence
beyond seven calendar days requires a fit note from a registered practitioner, submitted
to People Operations.

## Company sick pay

Employees with more than six months of service receive full pay for the first 20 working
days of absence in any rolling twelve-month period, and half pay for the following 20
working days. Thereafter, statutory provision applies.

## Return to work

A return-to-work conversation is held after every absence, regardless of length. Its
purpose is support and accurate recording, not disciplinary action.

## Long-term absence

Absence exceeding four consecutive weeks is managed as long-term absence, with a written
plan agreed between the employee, the line manager and People Operations.
""",
    ),
    Document(
        slug="parental-leave-policy",
        title="Parental Leave Policy",
        classification="public",
        owner_group="people-operations",
        body="""
## Eligibility

Employees with 26 weeks of continuous service at the point of notification are eligible
for company parental leave. Employees with less service receive the provision required by
applicable local employment law.

## Primary carer leave

The primary carer is entitled to 26 weeks at full pay, followed by 13 weeks at half pay.
Leave must begin within eight weeks of the birth or placement.

## Secondary carer leave

The secondary carer is entitled to six weeks at full pay, which may be taken in up to
three separate blocks within the first year.

## Notification

Notification should be given at least 15 weeks before the expected date where known.
Notification of an adoption placement should be given within seven days of the match
being confirmed.

## Return to work

An employee returning from parental leave returns to the same role. Where the role no
longer exists, a suitable alternative at the same band is offered.
""",
    ),
    Document(
        slug="probation-policy",
        title="Probation Policy",
        classification="public",
        owner_group="people-operations",
        body="""
## Standard period

The standard probationary period is six months from the start date for all roles up to
Band 5, and three months for Band 6 and above.

## Reviews

A formal review is held at the midpoint and at the end of the period. Both are recorded
in writing and shared with the employee within five working days.

## Extension

Probation may be extended once, by a maximum of three months, where a specific and
documented improvement is required. An extension must be confirmed in writing before the
original end date.

## Notice during probation

Either party may end the employment during probation with two weeks of notice. This
replaces the contractual notice period, which applies from confirmation onwards.

## Confirmation

Where no action is taken by the end date, probation is treated as passed and employment
is confirmed automatically.
""",
    ),
    Document(
        slug="performance-review-cycle",
        title="Performance Review Cycle",
        classification="internal",
        owner_group="people-operations",
        body="""
## Cycle

Northwind Logistics runs a single annual review cycle. Objectives are agreed in January,
a lightweight checkpoint is held in July, and the review conversation takes place in
November.

## Ratings

Four ratings are used: developing, effective, strong, and exceptional. There is no forced
distribution. Managers are asked to justify any rating of exceptional with specific
evidence.

## Calibration

Ratings are calibrated in departmental sessions before they are shared, so that standards
are consistent between teams. Calibration notes are retained by People Operations and are
not shared with employees.

## Relationship to pay

The review outcome is an input to the pay decision but does not determine it
mechanically. Pay decisions are made separately in the following February.

## Disagreement

An employee who disagrees with a rating may add a written comment to the record. The
comment is retained with the review and is visible to the next reviewing manager.
""",
    ),
    Document(
        slug="code-of-conduct",
        title="Code of Conduct",
        classification="public",
        owner_group="legal",
        body="""
## Purpose

This code sets the standard of behaviour expected of everyone working for or on behalf of
Northwind Logistics, including contractors and agency staff.

## Respect

Harassment, discrimination and bullying are not tolerated in any form, in any location,
including client sites, depots, vehicles and online channels.

## Conflicts of interest

Any personal interest that could reasonably be seen to influence a business decision must
be declared to your line manager in writing. Declaration is required even where you
believe the interest has no effect.

## Gifts and hospitality

Gifts with a value above 50 EUR may not be accepted. Hospitality above 100 EUR per person
requires prior approval from a department head and is recorded in the gifts register.

## Raising a concern

Concerns may be raised with a line manager, with People Operations, or through the
confidential whistleblowing channel. Retaliation against anyone raising a concern in good
faith is itself a disciplinary matter.
""",
    ),
    Document(
        slug="anti-bribery-policy",
        title="Anti-Bribery and Corruption Policy",
        classification="internal",
        owner_group="legal",
        body="""
## Position

Northwind Logistics prohibits bribery in all forms, whether offered, given, requested or
received, and whether directly or through a third party.

## Facilitation payments

Facilitation payments are prohibited without exception, including small payments to
expedite routine customs or permit processing. Where a payment is demanded under duress
and personal safety is at risk, the payment may be made and must be reported to Legal
within 24 hours.

## Third parties

Agents, brokers and customs intermediaries are subject to due diligence before
appointment and are re-screened every two years. Contracts must include the standard
anti-bribery clause.

## Record keeping

All payments to third parties must be supported by an invoice describing the service
performed. Round-sum payments without a described service are prohibited.

## Consequences

Breach of this policy is gross misconduct and may also be a criminal offence under
applicable local law.
""",
    ),
    Document(
        slug="acceptable-use-of-it",
        title="Acceptable Use of IT Systems",
        classification="internal",
        owner_group="security",
        body="""
## Scope

This policy covers all company-provided devices, accounts and network access, and any
personal device used to access company data.

## Personal use

Reasonable personal use of company devices is permitted provided it does not interfere
with work, consume significant bandwidth, or involve prohibited content.

## Prohibited activity

Installing unapproved software, disabling endpoint protection, connecting unmanaged
storage devices to depot systems, and sharing account credentials are all prohibited.

## Cloud services

Company data may only be stored in approved cloud services. Uploading company documents
to personal accounts or unapproved third-party tools is a security incident and must be
reported.

## Monitoring

System access is logged. Logs are reviewed only where there is a specific security or
policy concern, and any review beyond automated alerting requires authorisation from the
head of Security.
""",
    ),
    Document(
        slug="data-retention-schedule",
        title="Data Retention Schedule",
        classification="internal",
        owner_group="legal",
        body="""
## Principle

Data is retained only as long as there is a lawful and operational reason to keep it.
Retention periods run from the end of the relationship or the closure of the record,
whichever is later.

## Employee records

Core employee records are retained for six years after the end of employment.
Unsuccessful application records are retained for twelve months.

## Operational records

Consignment and delivery records are retained for seven years. Vehicle telematics data is
retained for 90 days, except where it relates to an open incident investigation.

## Security logs

System access logs are retained for 180 days. Logs relating to a reported incident are
retained until the investigation closes and then for a further two years.

## Deletion

Deletion is performed on a quarterly schedule. A record subject to a legal hold is
excluded from deletion until the hold is lifted by Legal.
""",
    ),
    Document(
        slug="expenses-approval-limits",
        title="Expenses and Procurement Approval Limits",
        classification="internal",
        owner_group="finance",
        body="""
## Approval thresholds

Expenditure up to 500 EUR may be approved by a line manager. Expenditure from 501 EUR to
5,000 EUR requires department head approval. Expenditure from 5,001 EUR to 50,000 EUR
requires finance director approval. Anything above 50,000 EUR requires board approval.

## Splitting

Splitting a purchase into smaller parts to stay below a threshold is prohibited and is
treated as a conduct matter. Related purchases from the same supplier within a single
quarter are assessed together.

## Purchase orders

A purchase order is required for any committed spend above 1,000 EUR. Invoices received
without a matching purchase order are held by Finance until one is raised.

## Emergency spend

Depot managers may authorise emergency spend up to 2,000 EUR where an operational
stoppage is in progress. The spend must be reported to Finance within one working day.

## Segregation of duties

The person who approves a purchase may not also approve the resulting invoice for
payment.
""",
    ),
    Document(
        slug="supplier-onboarding",
        title="Supplier Onboarding Procedure",
        classification="internal",
        owner_group="operations",
        body="""
## Purpose

This procedure governs how a new supplier is assessed and added to the approved supplier
register.

## Due diligence

All suppliers complete a due diligence questionnaire covering ownership, insurance,
subcontracting and sanctions exposure. Suppliers providing customs or brokerage services
additionally complete the anti-bribery screening.

## Insurance

Hauliers must evidence goods-in-transit cover of at least 250,000 EUR per vehicle and
public liability cover of at least 5,000,000 EUR. Certificates are checked at onboarding
and at each annual renewal.

## Trial period

New hauliers operate under a 90-day trial during which performance is reviewed monthly
against agreed on-time delivery and damage thresholds.

## Register

A supplier may not be paid until they appear on the approved supplier register. Adding a
supplier to the register requires two named approvers from different teams.
""",
    ),
    Document(
        slug="fleet-and-driver-safety",
        title="Fleet and Driver Safety Policy",
        classification="public",
        owner_group="operations",
        body="""
## Licence checks

Driving licences are checked at recruitment and every six months thereafter. A driver
whose licence check is overdue by more than 14 days is removed from the driving roster
until the check is completed.

## Vehicle checks

Drivers complete a walkaround check before the first journey of each shift and record it
in the fleet system. Defects classified as safety-critical remove the vehicle from
service immediately.

## Rest and hours

Driving hours follow applicable local law. Where company rules are stricter, the company
rule applies. Drivers must take a break of at least 45 minutes after four and a half
hours of driving.

## Incidents

All collisions, however minor, are reported to the depot manager before the end of the
shift. Photographs of the scene are taken where it is safe to do so.

## Telematics

Vehicles are fitted with telematics recording location, speed and harsh braking. Data is
used for safety and route planning, and is retained for 90 days.
""",
    ),
    Document(
        slug="warehouse-health-and-safety",
        title="Warehouse Health and Safety Standard",
        classification="public",
        owner_group="operations",
        body="""
## Personal protective equipment

High-visibility clothing and safety footwear are mandatory in all operational areas of
every depot. Bump caps are required in racking aisles.

## Segregation

Pedestrian walkways are physically segregated from forklift routes. Where segregation is
not possible at a loading door, a supervised crossing procedure is used.

## Forklift operation

Only operators holding a current certificate and a company authorisation may operate
forklift equipment. Authorisation is withdrawn immediately following a reportable
incident, pending review.

## Manual handling

Loads above 23 kilograms require either two people or mechanical assistance. Manual
handling training is refreshed every two years.

## Reporting

Near misses are reported through the same channel as accidents. The company treats near
miss reporting as a positive indicator and does not attach blame to it.
""",
    ),
    Document(
        slug="incident-response-procedure",
        title="Security Incident Response Procedure",
        classification="internal",
        owner_group="security",
        body="""
## Declaration

Any suspected compromise of a system or data set is declared as an incident by the head
of Security or a nominated deputy. Declaration does not require confirmation that a
breach has occurred.

## Severity

Severity 1 covers confirmed loss of customer data or loss of an operational system.
Severity 2 covers suspected loss without confirmation. Severity 3 covers contained events
with no data exposure.

## Response times

A Severity 1 incident requires an initial response within 30 minutes and a written update
every two hours until contained. Severity 2 requires a response within four hours.

## Communications

Only the incident lead communicates externally. Employees must not discuss an open
incident outside the response team, including with customers.

## Post-incident review

A written review is completed within ten working days of closure and records causes,
timeline and actions, without attributing individual blame.
""",
    ),
    Document(
        slug="business-continuity-plan",
        title="Business Continuity Plan Summary",
        classification="internal",
        owner_group="operations",
        body="""
## Purpose

This summary describes how Northwind Logistics maintains service during a significant
disruption. The full plan is held by the operations directorate.

## Recovery objectives

The recovery time objective for depot dispatch systems is four hours. The recovery point
objective for consignment data is 15 minutes.

## Depot loss

Where a depot becomes unavailable, its volume is redistributed to the two nearest depots
under a pre-agreed allocation. Redistribution is authorised by the operations director.

## Systems failure

Depots hold printed manifests for the current day so that dispatch can continue without
system access. Manifests are destroyed securely at the end of each day.

## Testing

The plan is tested twice a year. At least one test each year is unannounced.
""",
    ),
    Document(
        slug="training-and-development",
        title="Training and Development Policy",
        classification="public",
        owner_group="people-operations",
        body="""
## Budget

Each employee has an annual development budget of 1,200 EUR. The budget does not carry
over between years.

## Approval

Development spend within the budget is approved by the line manager. Spend above the
budget requires department head approval and a business justification.

## Study leave

Up to five days of paid study leave per year are available for an approved qualification
that is relevant to the role.

## Repayment

Where the company funds a qualification costing more than 3,000 EUR, a repayment
agreement applies: 100 per cent if the employee leaves within 12 months of completion, 50
per cent within 24 months, and nothing thereafter.

## Mandatory training

Health and safety, information security and code of conduct training are mandatory
annually and are not funded from the development budget.
""",
    ),
    Document(
        slug="internal-mobility",
        title="Internal Mobility and Vacancies",
        classification="public",
        owner_group="people-operations",
        body="""
## Advertising

Vacancies are advertised internally for five working days before any external
advertising, except where a role is filled by direct succession from a documented plan.

## Eligibility

Employees are eligible to apply after 12 months in their current role and where they are
not in a live formal performance or disciplinary process.

## Informing your manager

Applicants inform their line manager when invited to a first interview, not before. A
manager may not block an application.

## Transfer timing

Where an internal move is agreed, the standard handover period is eight weeks for
operational roles and four weeks for other roles.

## Unsuccessful applications

Feedback is offered to every internal applicant who reaches interview, within ten working
days of the decision.
""",
    ),
    Document(
        slug="whistleblowing-policy",
        title="Whistleblowing Policy",
        classification="public",
        owner_group="legal",
        body="""
## What is covered

This policy covers reports of criminal conduct, danger to health and safety, damage to
the environment, breach of legal obligation, and deliberate concealment of any of these.

## Channels

Concerns may be raised with any department head, with Legal, or through the independent
external reporting line, which accepts anonymous reports.

## Anonymity

A report made through the external line is passed to Legal without identifying details
unless the reporter chooses to be identified. Anonymity may limit how far an
investigation can proceed, and this is explained at the point of reporting.

## Protection

An employee raising a concern in good faith is protected from detriment, whether or not
the concern is upheld. Causing detriment to such a person is gross misconduct.

## Acknowledgement

Reports are acknowledged within five working days where a contact route exists, and an
outcome summary is provided where possible.
""",
    ),
    Document(
        slug="disciplinary-procedure",
        title="Disciplinary Procedure",
        classification="restricted",
        owner_group="people-operations",
        body="""
## Scope

This procedure is restricted to People Operations and to managers conducting a live case,
because it contains the standards applied to individual conduct decisions.

## Stages

The stages are: informal discussion, first written warning, final written warning, and
dismissal. Serious cases may begin at any stage.

## Warning duration

A first written warning remains live for six months. A final written warning remains live
for twelve months. Expired warnings are disregarded in later decisions.

## Gross misconduct

Gross misconduct may result in dismissal without notice. Examples include theft, violence,
falsification of records, working under the influence of alcohol or drugs in an
operational area, and deliberate breach of the anti-bribery policy.

## Suspension

Suspension is a neutral act, is on full pay, and is used only where continued attendance
would prejudice an investigation or present a risk.

## Appeal

An employee may appeal within ten working days. The appeal is heard by a manager not
previously involved.
""",
    ),
    Document(
        slug="redundancy-procedure",
        title="Redundancy Procedure",
        classification="restricted",
        owner_group="people-operations",
        body="""
## Scope

This document is restricted. Its existence and contents must not be discussed outside
People Operations and the executive team except during a live consultation.

## Selection

Where selection is required, the criteria are skills and qualifications, performance
record over the preceding two years, and disciplinary record for live warnings only.
Length of service is not a selection criterion.

## Consultation

Individual consultation comprises a minimum of three meetings. Collective consultation
applies where 20 or more roles are affected at one establishment and lasts a minimum of
30 days.

## Redundancy payment

The company payment is two weeks of pay per completed year of service, to a maximum of 20
years, in addition to any statutory entitlement.

## Alternative roles

Suitable alternative roles are offered before notice is issued, with a four-week trial
period that does not prejudice the redundancy entitlement if unsuccessful.
""",
    ),
    Document(
        slug="executive-succession-plan",
        title="Executive Succession Plan",
        classification="restricted",
        owner_group="people-operations",
        body="""
## Purpose

This plan records readiness assessments for executive and Band 6 leadership roles. It is
restricted to the Chief People Officer and the board.

## Readiness categories

Successors are recorded as ready now, ready in one to two years, or long-term potential.
Assessments are reviewed twice a year.

## Emergency cover

Every executive role has a named emergency cover who can act within 48 hours. Emergency
cover assignments are communicated only to the individuals concerned.

## Disclosure

Individuals are not routinely told their readiness category, because the assessment is a
planning instrument rather than a commitment. Where a development plan depends on it, the
Chief People Officer may disclose it.

## Retention

Assessments are retained for three years and are excluded from routine subject access
disclosure only where a legal exemption applies.
""",
    ),
    Document(
        slug="onboarding-checklist",
        title="Onboarding Checklist",
        classification="public",
        owner_group="people-operations",
        body="""
## Before the start date

People Operations issues the contract and the right-to-work check. IT provisions the
laptop and accounts. The line manager assigns a buddy from the same team.

## First day

The employee completes the health and safety induction before entering any operational
area. Depot-based starters additionally complete the site-specific induction.

## First week

Mandatory training on information security and the code of conduct is completed within
the first five working days. Access to systems beyond email is granted only once security
training is complete.

## First month

The line manager and the employee agree initial objectives within 20 working days of the
start date, and these form the basis of the midpoint probation review.

## Buddy

The buddy is a peer, not a manager, and the arrangement runs for the first three months.
""",
    ),
]


EVAL_QUESTIONS: list[EvalQuestion] = [
    # --- Answerable: each maps to exactly one document holding the fact. ---
    EvalQuestion(
        "How many days in advance must domestic flights be booked?",
        "travel-expense-policy",
        "fourteen days",
    ),
    EvalQuestion(
        "What is the daily meal allowance for international travel?",
        "travel-expense-policy",
        "65 EUR",
    ),
    EvalQuestion(
        "How many days per week must hybrid employees attend the office?",
        "remote-working-policy",
        "a minimum of two days",
    ),
    EvalQuestion(
        "How long can an employee work from another country?",
        "remote-working-policy",
        "20 working days per calendar year",
    ),
    EvalQuestion(
        "How much annual leave do full-time employees receive?",
        "annual-leave-policy",
        "26 days",
    ),
    EvalQuestion(
        "How many days of annual leave can be carried over, and by when must they be used?",
        "annual-leave-policy",
        "five days, by 31 March",
    ),
    EvalQuestion(
        "How many days of absence can be self-certified before a fit note is required?",
        "sickness-absence-policy",
        "up to seven consecutive calendar days",
    ),
    EvalQuestion(
        "How long is company sick pay paid at full pay?",
        "sickness-absence-policy",
        "the first 20 working days",
    ),
    EvalQuestion(
        "How much leave is the primary carer entitled to?",
        "parental-leave-policy",
        "26 weeks at full pay followed by 13 weeks at half pay",
    ),
    EvalQuestion(
        "How long is the standard probationary period?",
        "probation-policy",
        "six months up to Band 5, three months for Band 6 and above",
    ),
    EvalQuestion(
        "What notice applies during probation?",
        "probation-policy",
        "two weeks",
    ),
    EvalQuestion(
        "What performance ratings does the company use?",
        "performance-review-cycle",
        "developing, effective, strong, exceptional",
    ),
    EvalQuestion(
        "What is the maximum value of a gift that may be accepted?",
        "code-of-conduct",
        "50 EUR",
    ),
    EvalQuestion(
        "Are facilitation payments allowed?",
        "anti-bribery-policy",
        "prohibited without exception",
    ),
    EvalQuestion(
        "How long are vehicle telematics records kept?",
        "data-retention-schedule",
        "90 days",
    ),
    EvalQuestion(
        "Who can approve expenditure of 20,000 EUR?",
        "expenses-approval-limits",
        "the finance director",
    ),
    EvalQuestion(
        "What goods-in-transit insurance must hauliers evidence?",
        "supplier-onboarding",
        "at least 250,000 EUR per vehicle",
    ),
    EvalQuestion(
        "How often are driving licences checked?",
        "fleet-and-driver-safety",
        "every six months",
    ),
    EvalQuestion(
        "What weight of load requires two people or mechanical assistance?",
        "warehouse-health-and-safety",
        "above 23 kilograms",
    ),
    EvalQuestion(
        "What is the annual development budget per employee?",
        "training-and-development",
        "1,200 EUR",
    ),
    # --- Unanswerable by design. These matter most: they test whether the
    # --- system admits ignorance instead of inventing something plausible.
    EvalQuestion("What is the company's pension contribution rate?", None),
    EvalQuestion("How many employees work at the Rotterdam depot?", None),
    EvalQuestion("What was Northwind Logistics' revenue last year?", None),
    EvalQuestion("What is the policy on keeping pets in company accommodation?", None),
    EvalQuestion("Which insurance provider underwrites the company fleet?", None),
]
