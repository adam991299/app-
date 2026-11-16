"""Change the risk level until the app has its button (which will ask for a passkey):

python -m jarvis.store.profile offensiv     (försiktig | balanserad | offensiv)
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

from jarvis.risk.profiles import NAMES_SV, RiskProfile
from jarvis.store.db import create_engine, database_url_from_env
from jarvis.store.repo import Store

BY_NAME = {name.lower(): profile for profile, name in NAMES_SV.items()}


def parse(argv: Sequence[str]) -> RiskProfile:
    if len(argv) != 1 or argv[0].lower() not in BY_NAME:
        raise ValueError("ange försiktig, balanserad eller offensiv")
    return BY_NAME[argv[0].lower()]


def main(argv: Sequence[str]) -> int:  # pragma: no cover - thin shell around the store
    try:
        profile = parse(argv)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    store = Store(create_engine(database_url_from_env()))
    effective = asyncio.run(store.set_risk_profile(profile, actor="adam", at=datetime.now(UTC)))
    sys.stdout.write(f"Risknivå {NAMES_SV[profile]} gäller från {effective:%Y-%m-%d %H:%M} UTC\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
