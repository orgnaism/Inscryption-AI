from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inscryption_card_generator.schema_compat import parse_analysis
from inscryption_card_generator.rules import generate_card_data


def test_generate_card_data_bounds():
    obj = parse_analysis((ROOT / 'examples' / 'pinecone.json').read_text())
    for i in range(3):
        card = generate_card_data(obj, variant=i)
        assert 2 <= card.attack <= 4
        assert 2 <= card.health <= 4
        assert 1 <= card.cost_blood <= 3
        assert card.name
        assert card.sigil_name
