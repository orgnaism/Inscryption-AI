import json
import os

import ollama


MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:3b")


PROMPT = """
Analyze the main physical object being intentionally shown in this image.

Ignore the person's hand, body, room, furniture, and background.

Return ONLY valid JSON in exactly this structure:

{
    "object_name": "string",
    "dominant_material": "metal|wood|glass|plastic|fabric|rubber|stone|ceramic|paper|leather|organic|electronic|mixed|unknown",
    "secondary_materials": [],
    "textures": [],
    "hardness": "soft|medium|hard",
    "flexibility": "rigid|semi_flexible|flexible",
    "size": "tiny|small|medium|large",
    "shape": "round|cylindrical|flat|angular|elongated|boxy|irregular",
    "reflective": true,
    "sharp": false,
    "organic": false,
    "electronic": false,
    "confidence": "low|medium|high",
    "visible_features": [],
    "subject_count": 1
}

For textures only use:
smooth, rough, fuzzy, woven, glossy, matte, sharp, soft,
ridged, segmented, irregular.

For visible_features list only features you can actually see, using:
fur, feathers, scales, skin, shell, carapace, wings, beak, claws, talons,
fangs, horns, antlers, tusks, hooves, tail, fins, quills, spines, thorns,
stinger, pincers, mandibles, antennae, many_legs, leaves, bark, petals,
seeds, blade, point. Use [] if none apply.

If several animals or objects are shown, describe the most prominent one,
name only that one in object_name, and set subject_count to how many there are.
Use the most specific common name you are sure of (for example "raven", not "bird").
If you are unsure what it is, say so with confidence "low".

Do not generate game stats or card abilities.
"""


class AnalysisError(RuntimeError):
    """The vision model could not be reached or did not return usable JSON."""


def parse_model_output(raw_output):
    # Remove markdown fences if model adds them, then take the outermost JSON object.
    raw_output = raw_output.replace("```json", "")
    raw_output = raw_output.replace("```", "")
    raw_output = raw_output.strip()

    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError:
        start, end = raw_output.find("{"), raw_output.rfind("}")
        if start == -1 or end <= start:
            raise AnalysisError(f"Model returned no JSON object: {raw_output[:200]!r}")
        try:
            data = json.loads(raw_output[start:end + 1])
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"Model returned invalid JSON ({exc}): {raw_output[:200]!r}") from None

    if not isinstance(data, dict):
        raise AnalysisError("Model returned JSON that is not an object")

    return data


def analyze_object(image_path):

    try:
        response = ollama.chat(
            model=MODEL,
            format="json",
            messages=[
                {
                    "role": "user",
                    "content": PROMPT,
                    "images": [image_path]
                }
            ]
        )
    except Exception as exc:
        raise AnalysisError(
            f"Image analysis request failed ({exc}). Is Ollama running and is '{MODEL}' pulled?"
        ) from exc

    raw_output = response["message"]["content"]

    return parse_model_output(raw_output)
