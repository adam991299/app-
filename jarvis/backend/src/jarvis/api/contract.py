"""Writes the API contract as JSON Schema to ``jarvis/contracts/api.schema.json``.

Run ``uv run python -m jarvis.api.contract`` after changing ``schemas``; a test fails if
the checked-in file is out of date, so the web app's types can never silently drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from jarvis.api.schemas import PortfolioOut, StatusOut, TodayOut, TradesOut

ENDPOINTS: dict[str, type[BaseModel]] = {
    "GET /api/status": StatusOut,
    "GET /api/portfolio": PortfolioOut,
    "GET /api/trades": TradesOut,
    "GET /api/today": TodayOut,
}

CONTRACT_PATH = Path(__file__).resolve().parents[4] / "contracts" / "api.schema.json"


def render() -> str:
    schema = {
        "title": "Jarvis API",
        "endpoints": {
            route: model.model_json_schema(mode="serialization", ref_template="#/$defs/{model}")
            for route, model in ENDPOINTS.items()
        },
    }
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    CONTRACT_PATH.write_text(render(), encoding="utf-8")
    sys.stdout.write(f"wrote {CONTRACT_PATH}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
