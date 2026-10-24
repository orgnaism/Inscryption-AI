from __future__ import annotations


def make_portrait_prompt(obj, card) -> str:
    secondary = ", ".join(obj.secondary_materials) if obj.secondary_materials else "none"
    textures = ", ".join(obj.textures) if obj.textures else "plain"
    kind = getattr(card, "subject_kind", "animal")
    if kind == "animal":
        subject = (f"Create a single 2D illustration of a {obj.object_name}, shown as the animal it is, "
                   f"for an Inscryption Act 1 creature card named \"{card.name}\".")
    else:
        # Non-animals are drawn as themselves: no invented faces, limbs or biology.
        subject = (f"Create a single 2D illustration of a {obj.object_name}, shown as the {kind} it is, "
                   f"for an Inscryption Act 1 card named \"{card.name}\". Do not give it a face, eyes, mouth, "
                   f"limbs, claws, teeth or any other creature features.")
    return f"""{subject}
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
Gameplay flavor: tribe={card.tribe}, sigils={card.sigil_name}, attack={card.attack}, health={card.health}.
Style requirements: dark ink-and-charcoal woodcut look like Inscryption's Act 1 cards, moody horror-fantasy tone, crisp silhouette, earthy muted palette, readable when shrunk to 114x94 pixels, subject centered and filling most of a wide frame, plain flat solid light-grey background (it is removed afterwards), no text, no border, no UI.
It must be an original design, not a copy of an existing game card."""
