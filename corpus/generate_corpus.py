"""Generate the synthetic public demo corpus.

Every document produced here is invented. See corpus/README.md for why this exists
and how the classifications map onto the seeded ACL.

Deterministic by design: the same --seed produces byte-identical output, so eval
numbers computed against the corpus are reproducible.

    python corpus/generate_corpus.py --out ~/.rag-enterprise/uploads
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path

COMPANY = "Northwind Logistics"


@dataclass(frozen=True)
class Document:
    """One synthetic document plus the metadata the seed pack needs."""

    slug: str
    title: str
    classification: str  # public | internal | restricted
    owner_group: str
    body: str

    def filename(self) -> str:
        return f"{self.slug}.md"

    def render(self) -> str:
        return f"# {self.title}\n\n{self.body.strip()}\n"


def _documents() -> list[Document]:
    """The corpus definition.

    Kept as data rather than generated prose: a reader must be able to see exactly
    what the system was asked about, and hand-written policy text reads like the
    real thing in a way that templated filler does not.
    """
    return [
        Document(
            slug="travel-expense-policy",
            title="Travel and Expense Policy",
            classification="public",
            owner_group="finance",
            body=f"""
## Scope

This policy applies to all {COMPANY} employees travelling on company business.

## Booking

Domestic flights must be booked at least fourteen days in advance where the itinerary
is known. Economy class is the standard for all flights under six hours. Flights of six
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
            body=f"""
## Eligibility

All {COMPANY} employees whose role does not require physical presence at a depot are
eligible for hybrid working. Depot operations roles are excluded because the work
cannot be performed remotely.

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
restricted to People Operations and the executive team. It must not be shared with
line managers outside the review process.

## Bands

Band 3 (Associate): 38,000 to 47,000 EUR.
Band 4 (Professional): 46,000 to 61,000 EUR.
Band 5 (Senior): 60,000 to 79,000 EUR.
Band 6 (Lead): 76,000 to 98,000 EUR.

Bands overlap deliberately so that progression does not require a title change.

## Off-band offers

Any offer above the top of a band requires written approval from the Chief People
Officer and a documented market justification.
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
writing to People Operations. Where the grievance concerns the line manager, it should
be raised directly with People Operations.

## Timescales

A formal grievance is acknowledged within five working days. A hearing is normally held
within fifteen working days of acknowledgement.

## Right to be accompanied

An employee may be accompanied at any formal hearing by a colleague or a trade union
representative.

## Appeals

An employee may appeal the outcome within ten working days of receiving it. The appeal
is heard by someone not involved in the original decision.
""",
        ),
    ]


def write_corpus(out_dir: Path, documents: list[Document]) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for document in documents:
        path = out_dir / document.filename()
        path.write_text(document.render(), encoding="utf-8")
        written.append(document.filename())

    # The manifest is what the seed pack reads: it carries the classification and
    # owning group that become ACL grants, so access control is defined alongside
    # the documents rather than configured separately and drifting.
    manifest = {
        "corpus": "northwind-public-demo",
        "synthetic": True,
        "note": "Every document is invented. No real company or person is represented.",
        "documents": [asdict(d) | {"filename": d.filename(), "body": None} for d in documents],
    }
    (out_dir / "corpus-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"out_dir": str(out_dir), "written": written, "count": len(written)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="~/.rag-enterprise/uploads",
        help="Directory to write the corpus into (default: ~/.rag-enterprise/uploads).",
    )
    parser.add_argument("--seed", type=int, default=0, help="Reserved for future generated variation.")
    args = parser.parse_args()

    result = write_corpus(Path(args.out).expanduser(), _documents())
    print(f"Wrote {result['count']} synthetic documents to {result['out_dir']}")
    for name in result["written"]:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
