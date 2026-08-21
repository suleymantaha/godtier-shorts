from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from backend.services.abuse.risk_engine import RiskSignals
from backend.services.abuse.trial_service import (
    SqlAlchemyRiskEventWriter,
    TrialAction,
    TrialRiskRequest,
    TrialRiskService,
)


class RecordingWriter:
    def __init__(self) -> None:
        self.calls = []

    async def record(self, **kwargs) -> None:
        self.calls.append(kwargs)


@pytest.mark.parametrize(
    ("signals", "expected_action"),
    [
        (RiskSignals(), TrialAction.FREE_SCAN),
        (
            RiskSignals(account_age_minutes=5, turnstile_valid=False),
            TrialAction.CHALLENGE,
        ),
        (RiskSignals(known_trial_identity=True), TrialAction.PAYMENT_REQUIRED),
        (RiskSignals(clerk_bot_detected=True), TrialAction.BLOCK_REVIEW),
    ],
)
def test_trial_service_maps_risk_to_product_action(
    signals: RiskSignals, expected_action: TrialAction
) -> None:
    writer = RecordingWriter()
    request = TrialRiskRequest(
        request_id="request-123",
        user_id=uuid4(),
        signals=signals,
    )

    decision = asyncio.run(TrialRiskService(event_writer=writer).evaluate(request))

    assert decision.action is expected_action
    assert len(writer.calls) == 1
    assert writer.calls[0]["request_id"] == "request-123"
    assert writer.calls[0]["assessment"] == decision.assessment


def test_trial_service_rejects_missing_request_identity() -> None:
    with pytest.raises(ValueError, match="request_id"):
        TrialRiskRequest(request_id=" ", user_id=uuid4(), signals=RiskSignals())


def test_sql_writer_persists_only_hashed_identity_evidence() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.rows = []
            self.commits = 0

        def add(self, row) -> None:
            self.rows.append(row)

        async def commit(self) -> None:
            self.commits += 1

    session = FakeSession()
    source_hash = "b" * 64
    request = TrialRiskRequest(
        request_id="request-hash",
        user_id=uuid4(),
        signals=RiskSignals(
            source_fingerprint_hash=source_hash,
            source_fingerprint_uses_24h=3,
        ),
    )

    asyncio.run(
        TrialRiskService(
            event_writer=SqlAlchemyRiskEventWriter(session),  # type: ignore[arg-type]
        ).evaluate(request)
    )

    assert session.commits == 1
    assert [row.signal for row in session.rows] == [
        "source_fingerprint_reuse",
        "risk_decision",
    ]
    assert session.rows[0].value_hash == source_hash
    assert all("raw_ip" not in row.metadata_json for row in session.rows)
