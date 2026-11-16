"""Register a deposit or withdrawal so the loss limits do not see it as trading.

python -m jarvis.store.flows 10000 "Insättning november"
python -m jarvis.store.flows -5000 "Uttag"
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from jarvis.store.db import create_engine, database_url_from_env
from jarvis.store.repo import Store


def parse(argv: Sequence[str]) -> tuple[Decimal, str]:
    if not argv:
        raise ValueError("ange belopp, t.ex. 10000 eller -5000")
    try:
        amount = Decimal(argv[0].replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"ogiltigt belopp: {argv[0]}") from exc
    note = " ".join(argv[1:]) or ("Insättning" if amount > 0 else "Uttag")
    return amount, note


async def register(store: Store, amount: Decimal, note: str) -> None:
    await store.record_cash_flow(amount, at=datetime.now(UTC), note=note)


def main(argv: Sequence[str]) -> int:  # pragma: no cover - thin shell around register
    try:
        amount, note = parse(argv)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    asyncio.run(register(Store(create_engine(database_url_from_env())), amount, note))
    sys.stdout.write(f"Registrerat: {amount} kr ({note})\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
