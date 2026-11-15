from jarvis.risk.reasons import MESSAGES_SV, Reason, message_sv


def test_every_reason_has_a_swedish_message() -> None:
    assert set(MESSAGES_SV) == set(Reason)
    for reason in Reason:
        text = message_sv(reason)
        assert text.endswith(".")
        assert "!" not in text  # calm tone (§9.1)
