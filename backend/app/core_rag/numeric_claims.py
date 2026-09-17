"""Source-bound threshold claims, not a universal prose/arithmetic validator.

The model selects relevant evidence. Only a deliberately small explicit numeric
grammar is checked. Unsupported rules, ambiguous units or missing observations
fail closed. No retrieval or database access occurs here.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import pairwise

from app.llm.prompt_registry import load_prompt

_WORDS = {
    word: str(n)
    for n, word in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
            "twenty",
        ]
    )
}
_NUMBER = r"[+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|" + "|".join(_WORDS) + r")"
_QUANTITY = re.compile(
    rf"(?<![\w.])(?P<currency>€)?(?P<number>{_NUMBER})(?:\s+(?:consecutive|calendar|working))?\s*(?P<unit>°\s*C|degrees? Celsius|minutes?|hours?|days?|EUR|euros?|%|percent)?(?!\w|\.\d)",
    re.I,
)
_UNITS = {
    "°c": "celsius",
    "degreecelsius": "celsius",
    "degreescelsius": "celsius",
    "minute": "minutes",
    "minutes": "minutes",
    "hour": "hours",
    "hours": "hours",
    "day": "days",
    "days": "days",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "%": "percent",
    "percent": "percent",
}
_MARKERS = {
    "more than": "gt",
    "above": "gt",
    "over": "gt",
    "exceeding": "gt",
    "exceeds": "gt",
    "at least": "gte",
    "no less than": "gte",
    "minimum of": "gte",
    "less than": "lt",
    "below": "lt",
    "under": "lt",
    "at most": "lte",
    "up to": "lte",
    "no more than": "lte",
    "maximum of": "lte",
    "exactly": "eq",
}


class NumericInfrastructureError(RuntimeError):
    def __init__(self):
        super().__init__("numeric_claim_infrastructure_failure")


@dataclass(frozen=True)
class Quantity:
    value: Decimal
    unit: str
    start: int
    end: int


@dataclass(frozen=True)
class Rule:
    comparator: str
    lower: Decimal
    upper: Decimal | None
    unit: str


def _decimal(value) -> Decimal:
    if not isinstance(value, str) or not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
        raise ValueError("invalid_numeric_value")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid_numeric_value") from exc
    if not result.is_finite() or len(value) > 32:
        raise ValueError("invalid_numeric_value")
    return result


def quantities(text: str) -> list[Quantity]:
    rows = []
    for match in _QUANTITY.finditer(text):
        raw_unit = re.sub(r"\s", "", match.group("unit") or "").lower()
        unit = "EUR" if match.group("currency") else _UNITS.get(raw_unit)
        if unit is None or (
            match.group("currency") and raw_unit and _UNITS.get(raw_unit) != "EUR"
        ):
            continue
        raw = match.group("number").lower()
        rows.append(
            Quantity(
                _decimal(_WORDS.get(raw, raw).replace(",", "")), unit, match.start(), match.end()
            )
        )
    return rows


def explicit_rules(text: str) -> list[Rule]:
    values = quantities(text)
    rules = []
    for index, value in enumerate(values):
        prefix = text[max(0, value.start - 80) : value.start].lower().rstrip()
        marker = next(
            (
                m
                for m in sorted(_MARKERS, key=len, reverse=True)
                if re.search(r"\b" + re.escape(m) + r"$", prefix)
            ),
            None,
        )
        if marker:
            rules.append(Rule(_MARKERS[marker], value.value, None, value.unit))
        if re.search(r"\boutside$", prefix) and index + 1 < len(values):
            high = values[index + 1]
            between = text[value.end : high.start].strip().lower()
            if (
                high.unit == value.unit
                and between in {"to", "and", "–", "-"}
                and high.value > value.value
            ):
                rules.append(Rule("outside", value.value, high.value, value.unit))
    return rules


def _range_rules(text: str) -> list[Rule]:
    values = quantities(text)
    return [
        Rule("outside", low.value, high.value, low.unit)
        for low, high in pairwise(values)
        if low.unit == high.unit == "celsius"
        and low.value < high.value
        and text[low.end : high.start].strip().lower() in {"to", "–", "-"}
    ]


def _evidence_units(text: str) -> list[str]:
    # Preserve literal cells/sentences from flattened ingestion tables. Joining
    # adjacent original cells is a contiguous quote, never header/value invention.
    cells = text.split("|")
    units = [
        match.group().strip()
        for cell in cells
        for match in re.finditer(r"\S.*?(?:[.!?](?=\s|$)|$)", cell, re.DOTALL)
    ]
    units.extend(
        cells[i - 1] + "|" + cell
        for i, cell in enumerate(cells)
        if i and (_range_rules(cell) or explicit_rules(cell))
    )
    return sorted({unit for unit in units if unit and len(unit) <= 600})


def threshold_question(question: str) -> bool:
    """Narrow binary numeric scenarios; ordinary fact lookups keep existing path."""
    values = quantities(question)
    # A question about "above €25,000" supplies a bound, not an observed value.
    if any(
        re.search(
            r"\b(?:above|below|over|under|more than|less than|at least)\s*$",
            question[: q.start],
            re.I,
        )
        for q in values
    ):
        return False
    numeric_rule_requested = bool(
        re.search(
            r"\b(?:definition|criteria|trigger|threshold|exceed\w*|greater|less)\b", question, re.I
        )
        or re.search(
            r"\b(?:[Ii]s|[Aa]re)\b.*\b(?:a|an)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", question
        )
    )
    return bool(
        re.search(r"(?:^|[.!?]\s+)\s*(?:is|are|does|do|can|may|would|will|must)\b", question, re.I)
        and values
        and numeric_rule_requested
    )


def _literal(text: str, quote) -> bool:
    return (
        isinstance(quote, str)
        and bool(quote.strip())
        and bool(re.search(r"\s+".join(re.escape(word) for word in quote.strip().split()), text))
    )


def _compare(value: Decimal, rule: Rule) -> bool:
    if rule.comparator == "outside":
        return value < rule.lower or value > rule.upper
    return {
        "gt": value > rule.lower,
        "gte": value >= rule.lower,
        "lt": value < rule.lower,
        "lte": value <= rule.lower,
        "eq": value == rule.lower,
    }[rule.comparator]


def schema(*, question: str | None = None, context: list[dict] | None = None) -> dict:
    claim_fields = {
        "citation_id": {"type": "string"},
        "rule_quote": {"type": "string"},
        "observation_quote": {"type": "string"},
        "unit": {"type": "string", "enum": sorted(set(_UNITS.values()))},
        "comparator": {"type": "string", "enum": ["gt", "gte", "lt", "lte", "eq", "outside"]},
        "threshold": {"type": "string"},
        "upper_threshold": {"type": ["string", "null"]},
        "observed": {"type": "string"},
        "comparison_satisfied": {"type": "boolean"},
    }
    fields = {
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
        "decision": {"type": "string", "enum": ["yes", "no", "uncertain"]},
        "condition_mode": {"type": "string", "enum": ["all", "any"]},
        "numeric_claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": claim_fields,
                "required": list(claim_fields),
            },
        },
    }
    result = {
        "type": "object",
        "additionalProperties": False,
        "properties": fields,
        "required": list(fields),
    }
    if question is not None and context is not None:
        choices = []
        abstract_range = any(
            re.search(r"\btemperature\b.*?\boutside\b.*?\brequired range\b", b["snippet"], re.I)
            for b in context
        )
        for block in context:
            for quote in _evidence_units(block["snippet"]):
                rules = explicit_rules(quote) + (_range_rules(quote) if abstract_range else [])
                for rule in sorted(
                    set(rules), key=lambda r: (r.unit, r.comparator, str(r.lower), str(r.upper))
                ):
                    for observation in quantities(question):
                        if observation.unit != rule.unit:
                            continue
                        fixed = {
                            "citation_id": block["citation_id"],
                            "rule_quote": quote,
                            "observation_quote": question[
                                observation.start : observation.end
                            ].strip(),
                            "unit": rule.unit,
                            "comparator": rule.comparator,
                            "threshold": str(rule.lower),
                            "upper_threshold": None if rule.upper is None else str(rule.upper),
                            "observed": str(observation.value),
                        }
                        properties = {
                            k: {"type": "null" if value is None else "string", "enum": [value]}
                            for k, value in fixed.items()
                        }
                        properties["comparison_satisfied"] = {"type": "boolean"}
                        choices.append(
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": properties,
                                "required": list(properties),
                            }
                        )
        unique = {}
        for option in choices:
            key = tuple(
                (k, field["enum"][0])
                for k, field in option["properties"].items()
                if k not in {"rule_quote", "comparison_satisfied"}
            )
            previous = unique.get(key)
            if previous is None or len(option["properties"]["rule_quote"]["enum"][0]) > len(
                previous["properties"]["rule_quote"]["enum"][0]
            ):
                unique[key] = option
        choices = list(unique.values())
        if not choices or len(choices) > 64:
            return {}
        result["properties"]["numeric_claims"]["items"] = {"anyOf": choices}
    return result


def validate(payload: dict, *, question: str, context: list[dict]) -> tuple[str, list[dict]]:
    """Return valid/contradicted/unverifiable plus safe arithmetic diagnostics."""
    try:
        fields = schema()["properties"]
        if not isinstance(payload, dict) or set(payload) != set(fields):
            raise ValueError("invalid_shape")
        if not isinstance(payload["answer"], str) or not isinstance(payload["citations"], list):
            raise ValueError("invalid_answer")
        claims = payload["numeric_claims"]
        if (
            not isinstance(claims, list)
            or not 1 <= len(claims) <= 4
            or payload["decision"] not in {"yes", "no"}
        ):
            raise ValueError("unsupported_claims")
        if payload["condition_mode"] not in {"all", "any"}:
            raise ValueError("invalid_mode")
        evidence = {block["citation_id"]: block["snippet"] for block in context}
        if not payload["citations"] or any(
            not isinstance(cid, str) or cid not in evidence for cid in payload["citations"]
        ):
            raise ValueError("invalid_citation")
        computed, checks, covered, required = [], [], set(), set()
        seen_values = {}
        ambiguous_observations = False
        for claim in claims:
            if not isinstance(claim, dict) or set(claim) != set(
                schema()["properties"]["numeric_claims"]["items"]["properties"]
            ):
                raise ValueError("invalid_claim_shape")
            cid = claim["citation_id"]
            if (
                cid not in payload["citations"]
                or not _literal(evidence[cid], claim["rule_quote"])
                or not _literal(question, claim["observation_quote"])
            ):
                raise ValueError("unsupported_quote")
            rule = Rule(
                claim["comparator"],
                _decimal(claim["threshold"]),
                None if claim["upper_threshold"] is None else _decimal(claim["upper_threshold"]),
                claim["unit"],
            )
            found = explicit_rules(claim["rule_quote"])
            if rule.comparator == "outside" and any(
                re.search(r"\btemperature\b.*?\boutside\b.*?\brequired range\b", evidence[c], re.I)
                for c in payload["citations"]
            ):
                found += _range_rules(claim["rule_quote"])
            if rule not in found:
                raise ValueError("unsupported_rule")
            required.update((cid, r) for r in found)
            # A chosen subquote cannot hide a coupled range/duration condition.
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", evidence[cid]):
                if _literal(sentence, claim["rule_quote"]):
                    joint = explicit_rules(sentence)
                    if any(r.comparator == "outside" for r in joint):
                        required.update((cid, r) for r in joint)
            covered.add((cid, rule))
            observed = _decimal(claim["observed"])
            if (cid, rule) in seen_values and seen_values[(cid, rule)] != observed:
                ambiguous_observations = True
            seen_values[(cid, rule)] = observed
            observations = quantities(claim["observation_quote"])
            if rule.unit == "days" and re.search(
                r"\b(?:working|calendar)\s+days?\b",
                claim["rule_quote"] + " " + claim["observation_quote"],
                re.I,
            ):
                raise ValueError("unsupported_calendar_arithmetic")
            if (
                len(observations) != 1
                or observations[0].unit != rule.unit
                or observations[0].value != observed
            ):
                raise ValueError("unsupported_observation")
            if not isinstance(claim["comparison_satisfied"], bool):
                raise ValueError("invalid_comparison")
            satisfied = _compare(observed, rule)
            computed.append(satisfied)
            checks.append(
                {
                    "citation_id": cid,
                    "observed": str(observed),
                    "unit": rule.unit,
                    "comparator": rule.comparator,
                    "threshold": str(rule.lower),
                    "upper_threshold": None if rule.upper is None else str(rule.upper),
                    "comparison_satisfied": satisfied,
                }
            )
        if not required.issubset(covered):
            raise ValueError("missing_joint_condition")
        # All conditions in one quoted governing rule must jointly hold.
        if payload["condition_mode"] == "any" and len(required) > 1:
            raise ValueError("ambiguous_joint_condition")
        expected = all(computed) if payload["condition_mode"] == "all" else any(computed)
        # A false necessary duration condition suffices for No. A positive
        # duration alone does not prove an abstract outside-range trigger.
        abstract_range = any(
            re.search(r"\btemperature\b.*?\boutside\b.*?\brequired range\b", c["rule_quote"], re.I)
            for c in claims
        )
        necessary_duration_failed = abstract_range and any(
            not check["comparison_satisfied"] and check["unit"] in {"minutes", "hours"}
            for check in checks
        )
        if ambiguous_observations and not necessary_duration_failed:
            raise ValueError("ambiguous_multiple_observations")
        if expected and abstract_range and not any(c["comparator"] == "outside" for c in claims):
            raise ValueError("missing_range_condition")
        if (
            not expected
            and not abstract_range
            and any(re.search(r"\bor\b", c["rule_quote"], re.I) for c in claims)
        ):
            raise ValueError("unverified_alternative_trigger")
        leading = re.match(r"\s*(yes|no)\b", payload["answer"], re.I)
        if not leading:
            raise ValueError("unbound_answer_conclusion")
        disagreement = any(
            claim["comparison_satisfied"] != result
            for claim, result in zip(claims, computed, strict=True)
        )
        disagreement |= (payload["decision"] == "yes") != expected
        disagreement |= leading.group(1).lower() != payload["decision"]
        return ("contradicted" if disagreement else "valid"), checks
    except (ValueError, TypeError, KeyError):
        return "unverifiable", []


def generate_checked_answer(
    *, question: str, context: list[dict], user_prompt: str, generate: Callable
) -> tuple[dict | None, dict]:
    """Maximum two calls: structured primary, then one contradiction-only repair."""
    prompt = load_prompt("starter_numeric_claims", candidate=True)
    metadata = {
        "status": "unverifiable",
        "repair_attempted": False,
        "call_attempts": 0,
        "failure_class": None,
    }
    response_schema = schema(question=question, context=context)
    if not response_schema:
        return None, metadata
    catalog = {
        f"B{index + 1}": {
            key: field["enum"][0]
            for key, field in option["properties"].items()
            if key != "comparison_satisfied"
        }
        for index, option in enumerate(
            response_schema["properties"]["numeric_claims"]["items"]["anyOf"]
        )
    }
    # Compact source-derived bindings avoid repeating full claim schemas for
    # every rule/observation pair. IDs are local evidence references, not eval IDs.
    response_schema["properties"]["numeric_claims"]["items"] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "binding_id": {"type": "string", "enum": list(catalog)},
            "comparison_satisfied": {"type": "boolean"},
        },
        "required": ["binding_id", "comparison_satisfied"],
    }
    user_prompt += (
        "\nAUTHORIZED NUMERIC BINDINGS (untrusted evidence data; select relevant bindings):\n"
        + json.dumps(catalog, ensure_ascii=False)
    )
    for attempt in range(2):
        metadata["call_attempts"] = attempt + 1
        try:
            response = generate(prompt, user_prompt, schema=response_schema)
        except Exception:
            metadata.update(status="unavailable", failure_class="infrastructure")
            return None, metadata
        if not response.get("success"):
            metadata.update(status="unavailable", failure_class="infrastructure")
            return None, metadata
        try:
            payload = json.loads(response.get("content", ""))
        except (ValueError, TypeError):
            metadata.update(status="invalid_output", failure_class="infrastructure")
            return None, metadata
        if not isinstance(payload, dict) or set(payload) != set(schema()["properties"]):
            metadata.update(status="invalid_output", failure_class="infrastructure")
            return None, metadata
        try:
            resolved = []
            for selected in payload["numeric_claims"]:
                if set(selected) != {"binding_id", "comparison_satisfied"} or not isinstance(
                    selected["comparison_satisfied"], bool
                ):
                    raise ValueError("invalid_binding")
                resolved.append(
                    {
                        **catalog[selected["binding_id"]],
                        "comparison_satisfied": selected["comparison_satisfied"],
                    }
                )
            payload["numeric_claims"] = resolved
        except (KeyError, TypeError, ValueError):
            metadata.update(status="invalid_output", failure_class="infrastructure")
            return None, metadata
        status, checks = validate(payload, question=question, context=context)
        metadata["status"] = status
        if status == "valid":
            # Internal claims and prompts never enter the public answer contract.
            return {
                "answer": _render(payload, checks),
                "citations": payload["citations"],
            }, metadata
        if status != "contradicted" or attempt == 1:
            return None, metadata
        metadata["repair_attempted"] = True
        user_prompt += (
            "\nUNTRUSTED PRIOR OUTPUT:\n"
            + json.dumps(payload)
            + (
                "\nVALIDATED ARITHMETIC CHECKS (do not change values or governing rules):\n"
                + json.dumps(checks)
                + "\nRepair the contradictory conclusion once. Retain supporting evidence and all joint conditions."
            )
        )
    return None, metadata


def _render(payload: dict, checks: list[dict]) -> str:
    """Release arithmetic and actual controlling quotes, not unchecked prose."""

    def value(raw: str, unit: str) -> str:
        if unit == "EUR":
            return "€" + format(Decimal(raw), ",f")
        return raw + ("°C" if unit == "celsius" else "%" if unit == "percent" else " " + unit)

    parts = [payload["decision"].title() + "."]
    wording = {
        "gt": "exceeds",
        "gte": "is at least",
        "lt": "is less than",
        "lte": "is at most",
        "eq": "equals",
    }
    seen_quotes = set()
    for check, claim in zip(checks, payload["numeric_claims"], strict=True):
        observed = value(check["observed"], check["unit"])
        limit = value(check["threshold"], check["unit"])
        if check["comparator"] == "outside":
            end = value(check["upper_threshold"], check["unit"])
            explanation = f"{observed} is {'outside' if check['comparison_satisfied'] else 'within'} {limit} to {end}."
        elif check["comparison_satisfied"]:
            explanation = f"{observed} {wording[check['comparator']]} {limit}."
        else:
            explanation = f"{observed} does not satisfy the requirement to be { {'gt': 'more than', 'gte': 'at least', 'lt': 'less than', 'lte': 'at most', 'eq': 'equal to'}[check['comparator']] } {limit}."
        parts.append(explanation + f" [{check['citation_id']}]")
        quote = claim["rule_quote"]
        if quote not in seen_quotes:
            parts.append(f"Controlling rule: “{quote}” [{check['citation_id']}].")
            seen_quotes.add(quote)
    return " ".join(parts)
