from __future__ import annotations

from decimal import Decimal

import pytest

from jarvis.store.flows import parse, register
from jarvis.store.repo import Store


def test_parse() -> None:
    assert parse(["10000"]) == (Decimal(10000), "Insättning")
    assert parse(["-5000,50", "Till", "semester"]) == (Decimal("-5000.50"), "Till semester")
    assert parse(["-1"])[1] == "Uttag"
    with pytest.raises(ValueError, match="ange belopp"):
        parse([])
    with pytest.raises(ValueError, match="ogiltigt"):
        parse(["mycket"])


async def test_register(store: Store) -> None:
    await register(store, Decimal(10000), "Insättning")
    assert (await store.audit_entries())[0][1] == "cash_flow"
