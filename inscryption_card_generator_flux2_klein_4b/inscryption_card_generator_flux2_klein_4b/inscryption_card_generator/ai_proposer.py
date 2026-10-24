"""Optional: let the local Ollama model PROPOSE a design (name, flavor, stats, sigils).

The proposal is structured JSON and is never trusted: ``sanitize_proposal`` keeps
only sigils that the rules already found eligible, keeps stats within
``ai_proposal.stat_tolerance`` of the deterministic estimate, and the result still
goes through balance.balance_design. Off by default (CLI flag --ai-propose).
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from .analysis import NormalizedAnalysis, extract_json_object
from .config import balance_rules, selectable_sigils
from .sigils import SigilChoice
from .taxonomy import Identification

DEFAULT_MODEL = os.getenv("OLLAMA_DESIGN_MODEL", os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:3b"))


class ProposalError(RuntimeError):
    pass


def build_prompt(a: NormalizedAnalysis, ident: Identification, tribe: str, eligible: list[SigilChoice],
                 attack: int, health: int) -> str:
    sigil_lines = "\n".join(f"- {s.display_name}: {selectable_sigils()[s.id]['effect']}" for s in eligible) or "- (none)"
    return f"""You are designing one Inscryption Act 1 card for a photographed subject.
Subject: {a.object_name} (kind: {ident.kind}, tribe: {tribe}).
Physical analysis: {json.dumps({k: a.raw.get(k) for k in a.raw if k != 'object_name'})}
Suggested stats: attack {attack}, health {health}. You may change each by at most 1.
You may choose 0, 1 or 2 sigils, ONLY from this list:
{sigil_lines}
Do not invent abilities, biology or game mechanics. Keep the name under 16 letters.
Return ONLY JSON: {{"display_name": "string", "description": "one short sentence", "attack": 0, "health": 1, "sigils": ["Sigil Name"]}}"""


def request_proposal(prompt: str, chat: Callable[..., Any] | None = None, model: str | None = None) -> dict[str, Any]:
    if chat is None:
        try:
            import ollama
        except ImportError as exc:
            raise ProposalError("The 'ollama' package is required for --ai-propose") from exc
        chat = ollama.chat
    try:
        response = chat(model=model or DEFAULT_MODEL, messages=[{"role": "user", "content": prompt}], format="json")
        content = response["message"]["content"]
    except Exception as exc:  # network errors, missing model, malformed response
        raise ProposalError(f"Design proposal request failed: {exc}") from exc
    try:
        return extract_json_object(content)
    except ValueError as exc:
        raise ProposalError(str(exc)) from exc


def sanitize_proposal(proposal: dict[str, Any], eligible: list[SigilChoice], attack: int, health: int) -> tuple[dict[str, Any], list[str]]:
    """Return the accepted subset of a proposal plus notes on everything rejected."""
    cfg = balance_rules()["ai_proposal"]
    tol = cfg["stat_tolerance"]
    by_name = {s.display_name.lower(): s.id for s in eligible} | {s.id.lower(): s.id for s in eligible}
    accepted: dict[str, Any] = {}
    notes: list[str] = []

    name = proposal.get("display_name")
    if isinstance(name, str) and re.fullmatch(r"[A-Za-z][A-Za-z' -]*", name.strip()) and len(name.strip()) <= cfg["max_name_length"]:
        accepted["display_name"] = name.strip()
    elif name is not None:
        notes.append(f"AI name {name!r} rejected (letters only, <= {cfg['max_name_length']} chars)")

    desc = proposal.get("description")
    if isinstance(desc, str) and desc.strip():
        clean = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f]", " ", desc)).strip()
        accepted["description"] = clean[:cfg["max_description_length"]]

    for key, base in (("attack", attack), ("health", health)):
        value = proposal.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            bounded = max(base - tol, min(base + tol, value))
            if bounded != value:
                notes.append(f"AI {key} {value} pulled back to {bounded} (must stay within {tol} of the rules' {base})")
            accepted[key] = bounded
        elif value is not None:
            notes.append(f"AI {key} {value!r} ignored (not an integer)")

    sigils = proposal.get("sigils")
    if isinstance(sigils, list):
        chosen: list[str] = []
        for item in sigils:
            sid = by_name.get(str(item).strip().lower())
            if sid is None:
                notes.append(f"AI sigil {item!r} rejected: not an eligible verified Act 1 sigil for this subject")
            elif sid not in chosen:
                chosen.append(sid)
        accepted["sigils"] = chosen
    return accepted, notes
