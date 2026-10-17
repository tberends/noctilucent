"""Contract between Python export and the browser loader in atmosphere.js."""

import re
from pathlib import Path

from src.sounding_plot import FIELDS, HEIGHT_COUNT

ATMOSPHERE_JS = Path(__file__).resolve().parents[1] / "app" / "scripts" / "atmosphere.js"


def test_field_order_matches_atmosphere_js_field_index():
    source = ATMOSPHERE_JS.read_text(encoding="utf-8")
    match = re.search(r"const FIELD_INDEX = \{([^}]+)\}", source, re.DOTALL)
    assert match, "FIELD_INDEX not found in atmosphere.js"
    pairs = re.findall(r"(\w+)\s*:\s*(\d+)", match.group(1))
    js_fields = [name for name, _index in sorted(pairs, key=lambda item: int(item[1]))]
    assert js_fields == FIELDS


def test_field_count_matches_export_fields():
    source = ATMOSPHERE_JS.read_text(encoding="utf-8")
    match = re.search(r"const FIELD_COUNT = (\d+);", source)
    assert match
    assert int(match.group(1)) == len(FIELDS)


def test_height_count_constant_is_positive():
    assert HEIGHT_COUNT == 80
