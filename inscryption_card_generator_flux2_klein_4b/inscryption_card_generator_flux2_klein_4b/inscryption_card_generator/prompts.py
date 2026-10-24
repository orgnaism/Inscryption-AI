from __future__ import annotations


def make_portrait_prompt(obj, card) -> str:
    secondary = ", ".join(obj.secondary_materials) if obj.secondary_materials else "none"
    textures = ", ".join(obj.textures) if obj.textures else "plain"
    return f"""Create a single 2D pixel-art creature portrait inspired by the real-world object \"{obj.object_name}\".
The creature's fantasy name is \"{card.name}\".
Use these physical properties from the scanned object:
- dominant material: {obj.dominant_material}
- secondary materials: {secondary}
- textures: {textures}
- hardness: {obj.hardness}
- flexibility: {obj.flexibility}
- size: {obj.size}
- shape: {obj.shape}
- reflective: {obj.reflective}
- sharp: {obj.sharp}
- organic: {obj.organic}
- electronic: {obj.electronic}
Gameplay flavor: tribe={card.tribe}, sigil={card.sigil_name}, attack={card.attack}, health={card.health}.
Style requirements: dark retro pixel art, moody horror-fantasy tone, crisp silhouette, earthy muted palette, readable at 128x128, subject centered, plain dark background, no text, no border, no UI.
The design should feel suitable for an Inscryption- or FloppyScryption-style card portrait, but must be an original creature design."""
