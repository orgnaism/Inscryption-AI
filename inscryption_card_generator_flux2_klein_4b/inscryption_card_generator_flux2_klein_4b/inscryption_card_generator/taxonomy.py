"""Stages 4-5: identify the photographed subject and assign an Inscryption tribe.

``object_name`` is the primary clue. It is matched token-by-token against
``data/taxonomy.json`` (longest phrase first, so "spider monkey" never becomes a
spider and "computer mouse" never becomes a mouse). The image JSON is then used
to reject impossible readings: an animal name on an electronic or inorganic
object is a toy, statue or picture ("depiction"), not a creature.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from typing import Any

from .analysis import NormalizedAnalysis
from .config import balance_rules, confidence_rank, taxonomy_table

ANIMAL_KINDS = {"animal", "colony"}
ANIMAL_FEATURES = {"fur", "feathers", "scales", "wings", "beak", "claws", "talons", "fangs", "horns",
                   "antlers", "tusks", "hooves", "fins", "antennae", "many_legs", "stinger", "pincers",
                   "mandibles", "carapace"}


@dataclass(frozen=True)
class SubjectEntry:
    match: tuple[str, ...]
    kind: str
    tribe: str | None
    traits: tuple[str, ...]
    names: tuple[str, ...]
    note: str | None


@dataclass
class Identification:
    object_name: str
    matched_phrase: str | None
    kind: str
    taxonomy_tribe: str
    traits: list[str]
    names: list[str]
    is_animal: bool
    is_group: bool
    supported: bool
    subjects: list[dict[str, Any]] = field(default_factory=list)
    multiple_subjects: bool = False
    tribe_conflict: bool = False
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TribeAssignment:
    tribe: str
    game_tribes: list[str]
    reason: str


@lru_cache(maxsize=1)
def _index() -> tuple[dict[tuple[str, ...], SubjectEntry], int]:
    table = taxonomy_table()
    index: dict[tuple[str, ...], SubjectEntry] = {}
    for raw in table["subjects"]:
        entry = SubjectEntry(
            match=tuple(raw["match"]),
            kind=raw["kind"],
            tribe=raw.get("tribe"),
            traits=tuple(raw.get("traits", [])),
            names=tuple(raw.get("names", [])),
            note=raw.get("note"),
        )
        for phrase in raw["match"]:
            index[tuple(_tokens(phrase))] = entry
    return index, max(len(k) for k in index)


def _tokens(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).split()


def singular(token: str) -> str:
    irregular = taxonomy_table()["irregular_plurals"]
    if token in irregular:
        return irregular[token]
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith(("ches", "shes", "sses", "xes", "zes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def _segments(object_name: str) -> list[list[str]]:
    separators = set(taxonomy_table()["segment_separators"])
    segments: list[list[str]] = []
    for chunk in re.split(r"[,&+/;]", object_name.lower()):
        current: list[str] = []
        for token in _tokens(chunk):
            if token in separators:
                if current:
                    segments.append(current)
                current = []
            else:
                current.append(token)
        if current:
            segments.append(current)
    return segments


def _match_segment(tokens: list[str]) -> list[dict[str, Any]]:
    index, max_len = _index()
    used = [False] * len(tokens)
    matches: list[dict[str, Any]] = []
    for n in range(min(max_len, len(tokens)), 0, -1):
        for start in range(0, len(tokens) - n + 1):
            if any(used[start:start + n]):
                continue
            window = tokens[start:start + n]
            plural = False
            entry = index.get(tuple(window))
            if entry is None:
                singular_window = window[:-1] + [singular(window[-1])]
                entry = index.get(tuple(singular_window))
                plural = entry is not None and singular_window != window
            if entry is None:
                continue
            for i in range(start, start + n):
                used[i] = True
            matches.append({"start": start, "end": start + n, "phrase": " ".join(window), "entry": entry, "plural": plural})
    return sorted(matches, key=lambda m: m["start"])


def _clean_display(text: str, limit: int = 16) -> str:
    """Title-case a phrase for the card; if it is too long, keep the head noun (the last word)."""
    words = [w.capitalize() for w in re.sub(r"[^A-Za-z']+", " ", text).split() if w.lower() not in {"a", "an", "the", "of"}]
    full = " ".join(words)
    if words and len(full) <= limit:
        return full
    return words[-1][:limit] if words else "Odd Curio"


def identify_subject(analysis: NormalizedAnalysis) -> Identification:
    table = taxonomy_table()
    depiction_words = set(table["depiction_words"])
    group_words = set(table["group_words"])

    found: list[dict[str, Any]] = []
    for segment in _segments(analysis.object_name):
        matches = _match_segment(segment)
        if not matches:
            continue
        head = matches[-1]  # English compounds put the head noun last: "deer skull" is a skull
        entry: SubjectEntry = head["entry"]
        depicted = entry.kind in ANIMAL_KINDS and bool(depiction_words & set(segment))
        animal_modifier = next((m for m in matches[:-1] if m["entry"].kind in ANIMAL_KINDS), None)
        if head["phrase"] in depiction_words and animal_modifier:  # "raven statue", "dog toy"
            head, entry, depicted = animal_modifier, animal_modifier["entry"], True
        found.append({
            "phrase": head["phrase"],
            "entry": entry,
            "segment": " ".join(segment),
            "depicted": depicted,
            "group": head["plural"] or bool(group_words & set(segment)) or any(t.isdigit() for t in segment),
        })

    reasons: list[str] = []
    notes: list[str] = []
    non_human = [f for f in found if f["entry"].kind != "human"]

    if not found or not non_human:
        if found:  # only people were named
            return Identification(analysis.object_name, found[0]["phrase"], "human", "Miscellaneous", [], [],
                                  False, False, False, reasons=["only a person/body part was identified; "
                                                                "the analyzer should ignore people, so a rescan is needed"])
        return _unidentified(analysis)

    primary = non_human[0]
    entry: SubjectEntry = primary["entry"]
    kind = entry.kind
    traits = list(entry.traits)
    names = list(entry.names) or [_clean_display(primary["phrase"])]
    if entry.note:
        notes.append(entry.note)
    reasons.append(f"'{analysis.object_name}' matched taxonomy phrase '{primary['phrase']}' "
                   f"(kind={kind}, taxonomy tribe={entry.tribe})")

    if kind in ANIMAL_KINDS:
        if primary["depicted"]:
            kind = "depiction"
            reasons.append("a depiction word (toy, statue, picture...) describes the animal, so it is not a living creature")
        elif analysis.electronic is True:
            kind = "depiction"
            reasons.append("electronic=true contradicts a living animal; treated as a depiction (e.g. a robot toy)")
        elif analysis.organic is False and analysis.dominant_material not in {"organic", "unknown"}:
            kind = "depiction"
            reasons.append(f"organic=false and dominant_material={analysis.dominant_material}; "
                           "treated as a depiction of the animal, not the animal itself")
    if kind == "depiction":
        traits = []
        names = [_clean_display(primary["segment"])]

    animal_subjects = [f for f in non_human if f["entry"].kind in ANIMAL_KINDS and not f["depicted"]]
    distinct_animals = {f["entry"].match for f in animal_subjects}
    multiple = len(distinct_animals) > 1
    tribe_conflict = len({f["entry"].tribe for f in animal_subjects}) > 1
    if multiple:
        others = ", ".join(f["phrase"] for f in animal_subjects[1:])
        reasons.append(f"several animals named; the first-named '{primary['phrase']}' is the card subject (others: {others})")
        if tribe_conflict:
            reasons.append("the named animals belong to different tribes")
    if len(non_human) > len(animal_subjects) and kind in ANIMAL_KINDS:
        notes.append("non-animal objects in the scan are treated as background")

    is_group = primary["group"] or analysis.subject_count > 1
    if is_group:
        reasons.append("the scan shows a group of the same subject")

    return Identification(
        object_name=analysis.object_name,
        matched_phrase=primary["phrase"],
        kind=kind,
        taxonomy_tribe=entry.tribe or "Miscellaneous",
        traits=traits,
        names=names,
        is_animal=kind in ANIMAL_KINDS,
        is_group=is_group,
        supported=True,
        subjects=[{"phrase": f["phrase"], "kind": f["entry"].kind, "tribe": f["entry"].tribe,
                   "depicted": f["depicted"]} for f in found],
        multiple_subjects=multiple,
        tribe_conflict=tribe_conflict,
        reasons=reasons,
        notes=notes,
    )


def _unidentified(analysis: NormalizedAnalysis) -> Identification:
    features = set(analysis.visible_features)
    if analysis.organic is True and features & ANIMAL_FEATURES and analysis.electronic is not True:
        kind, reason = "animal", (f"'{analysis.object_name}' is not in the taxonomy, but visible features "
                                  f"{sorted(features & ANIMAL_FEATURES)} indicate an unidentified creature")
    elif analysis.organic is True:
        kind, reason = "unknown", f"'{analysis.object_name}' is organic but unidentified; no biology is assumed"
    else:
        kind, reason = "object", f"'{analysis.object_name}' is not in the taxonomy; treated as a plain object"
    return Identification(analysis.object_name, None, kind, "Miscellaneous", [],
                          [_clean_display(analysis.object_name)], kind == "animal", analysis.subject_count > 1, True,
                          reasons=[reason])


def assign_tribe(identification: Identification, confidence: str) -> TribeAssignment:
    """Map the identification to one generator tribe and to the game's Tribe enum names."""
    game_ids = taxonomy_table()["tribe_game_ids"]
    allow = balance_rules()["confidence"][confidence]["allow_tribe"]
    if not identification.is_animal:
        reason = f"{identification.kind} subjects are never given an animal tribe"
        return TribeAssignment("Miscellaneous", game_ids["Miscellaneous"], reason)
    if not allow:
        return TribeAssignment("Miscellaneous", game_ids["Miscellaneous"],
                               f"{confidence} confidence: animal classification is not reliable enough for a tribe")
    tribe = identification.taxonomy_tribe
    reason = f"taxonomy entry for '{identification.matched_phrase}' is {tribe}"
    if tribe == "Miscellaneous":
        reason += " (Inscryption gives such animals no tribe)"
    return TribeAssignment(tribe, list(game_ids[tribe]), reason)


def confidence_after_identification(identification: Identification, confidence: str) -> tuple[str, list[str]]:
    """Lower confidence one step when the scan names animals from different tribes."""
    notes: list[str] = []
    if identification.tribe_conflict and confidence_rank(confidence) > 0:
        lowered = ["low", "medium", "high"][confidence_rank(confidence) - 1]
        notes.append(f"confidence lowered {confidence} -> {lowered}: animals from different tribes in one scan")
        return lowered, notes
    return confidence, notes
