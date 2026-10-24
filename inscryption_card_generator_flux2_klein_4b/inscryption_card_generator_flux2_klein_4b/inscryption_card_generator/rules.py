from __future__ import annotations

import hashlib
import random
from typing import Iterable

from .card_models import CardData

SIGILS = {
    "Sharp Quills": {
        "desc": "Strikes back when hit.",
        "when": lambda o: o.sharp or "sharp" in o.textures,
    },
    "Burrower": {
        "desc": "Moves when a lane is threatened.",
        "when": lambda o: o.size in {"tiny", "small"} and o.flexibility != "rigid",
    },
    "Armored": {
        "desc": "Blocks the first incoming damage.",
        "when": lambda o: o.hardness == "hard" or o.dominant_material in {"stone", "metal", "ceramic"},
    },
    "Sprinter": {
        "desc": "Moves sideways each turn.",
        "when": lambda o: o.shape == "elongated" or o.flexibility == "flexible",
    },
    "Loose Tail": {
        "desc": "Escapes and leaves something behind.",
        "when": lambda o: o.organic and o.flexibility != "rigid",
    },
    "Mighty Leap": {
        "desc": "Can block airborne threats.",
        "when": lambda o: o.shape in {"angular", "irregular", "round"},
    },
    "Battery Spark": {
        "desc": "Crackles with charged energy.",
        "when": lambda o: o.electronic or o.reflective,
    },
    "Bone Heap": {
        "desc": "Returns stronger from remains.",
        "when": lambda o: o.dominant_material in {"wood", "organic", "paper", "leather"},
    },
}

TRIBES = {
    "organic": "Woodland",
    "wood": "Woodland",
    "electronic": "Construct",
    "metal": "Construct",
    "ceramic": "Hooved",
    "glass": "Avian",
    "fabric": "Canine",
    "stone": "Reptile",
    "plastic": "Insect",
    "paper": "Insect",
    "leather": "Canine",
    "rubber": "Reptile",
    "mixed": "Woodland",
    "unknown": "Woodland",
}

PREFIX_BY_MATERIAL = {
    "wood": ["Bark", "Thorn", "Root", "Splinter"],
    "organic": ["Bramble", "Moss", "Thistle", "Feral"],
    "metal": ["Iron", "Rivet", "Rust", "Steel"],
    "glass": ["Shiver", "Gleam", "Shard", "Glint"],
    "ceramic": ["Kiln", "Clay", "Cinder", "Ash"],
    "fabric": ["Rag", "Tatter", "Velvet", "Snare"],
    "electronic": ["Volt", "Circuit", "Spark", "Static"],
    "stone": ["Gravel", "Basalt", "Crag", "Slate"],
    "plastic": ["Mold", "Snap", "Petro", "Hollow"],
    "paper": ["Scroll", "Fold", "Pulp", "Quill"],
    "leather": ["Hide", "Tannin", "Strap", "Whip"],
    "rubber": ["Tread", "Bounce", "Tar", "Grip"],
    "mixed": ["Odd", "Patch", "Weld", "Scrap"],
    "unknown": ["Crooked", "Strange", "Dusky", "Nameless"],
}

SUFFIX_BY_SHAPE = {
    "round": ["Orb", "Maw", "Pup", "Bulb"],
    "cylindrical": ["Spine", "Trunk", "Stalk", "Barrel"],
    "flat": ["Leaf", "Hide", "Wing", "Slab"],
    "angular": ["Fang", "Jaw", "Crest", "Shard"],
    "elongated": ["Tail", "Strider", "Needle", "Runner"],
    "boxy": ["Crate", "Hulk", "Block", "Brute"],
    "irregular": ["Maw", "Warden", "Crawler", "Stalker"],
}

RARITY_BY_CONFIDENCE = {"low": "Uncertain", "medium": "Common", "high": "Common"}


def _seed_from(obj, variant: int) -> int:
    basis = f"{obj.object_name}|{obj.dominant_material}|{obj.textures}|{variant}".encode()
    return int(hashlib.sha256(basis).hexdigest()[:16], 16)


def _pick(rng: random.Random, items: list[str]) -> str:
    return items[rng.randrange(len(items))]


def build_name(obj, rng: random.Random) -> str:
    prefix = _pick(rng, PREFIX_BY_MATERIAL.get(obj.dominant_material, PREFIX_BY_MATERIAL["unknown"]))
    suffix = _pick(rng, SUFFIX_BY_SHAPE.get(obj.shape, SUFFIX_BY_SHAPE["irregular"]))
    if obj.sharp and suffix not in {"Fang", "Needle", "Spine", "Shard"}:
        suffix = _pick(rng, ["Fang", "Needle", "Spine", "Shard"])
    return prefix + suffix


def choose_sigil(obj, rng: random.Random) -> tuple[str, str]:
    valid = [name for name, meta in SIGILS.items() if meta["when"](obj)]
    if not valid:
        valid = ["Mighty Leap"]
    sigil_name = _pick(rng, valid)
    return sigil_name, SIGILS[sigil_name]["desc"]


def compute_stats(obj, rng: random.Random) -> tuple[int, int]:
    attack = rng.randint(2, 4)
    health = rng.randint(2, 4)
    if obj.sharp:
        attack = min(4, attack + 1)
        health = max(2, health - 1)
    if obj.hardness == "hard":
        health = min(4, health + 1)
    if obj.size == "tiny":
        attack = max(2, attack - 1)
    if obj.size == "large":
        health = min(4, health + 1)
    if obj.flexibility == "flexible":
        attack = min(4, attack + 1)
    return max(2, min(4, attack)), max(2, min(4, health))


def compute_cost(attack: int, health: int, sigil_name: str) -> int:
    score = attack + health
    if sigil_name in {"Sharp Quills", "Armored", "Battery Spark"}:
        score += 1
    if score <= 5:
        return 1
    if score <= 7:
        return 2
    return 3


def build_lore(obj, name: str, sigil_name: str) -> str:
    textures = ", ".join(obj.textures[:2]) if obj.textures else "strange"
    return f"{name} was born from a {textures} {obj.object_name}; it bears the mark of {sigil_name}."


def generate_card_data(obj, variant: int = 0) -> CardData:
    rng = random.Random(_seed_from(obj, variant))
    name = build_name(obj, rng)
    attack, health = compute_stats(obj, rng)
    sigil_name, sigil_description = choose_sigil(obj, rng)
    cost = compute_cost(attack, health, sigil_name)
    tribe = TRIBES.get(obj.dominant_material, "Woodland")
    rarity = RARITY_BY_CONFIDENCE.get(obj.confidence, "Common")
    lore = build_lore(obj, name, sigil_name)
    return CardData(
        name=name,
        attack=attack,
        health=health,
        cost_blood=cost,
        sigil_name=sigil_name,
        sigil_description=sigil_description,
        tribe=tribe,
        rarity=rarity,
        lore=lore,
    )
