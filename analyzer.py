import json
import ollama


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
    "confidence": "low|medium|high"
}

For textures only use:
smooth, rough, fuzzy, woven, glossy, matte, sharp, soft,
ridged, segmented, irregular.

Do not generate game stats or card abilities.
"""


def analyze_object(image_path):

    response = ollama.chat(
        model="qwen2.5vl:3b",
        messages=[
            {
                "role": "user",
                "content": PROMPT,
                "images": [image_path]
            }
        ]
    )

    raw_output = response["message"]["content"]

    # Remove markdown fences if model adds them
    raw_output = raw_output.replace("```json", "")
    raw_output = raw_output.replace("```", "")
    raw_output = raw_output.strip()

    data = json.loads(raw_output)

    return data