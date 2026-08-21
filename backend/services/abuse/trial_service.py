from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RiskEvent
from backend.services.abuse.risk_engine import (
    RiskAssessment,
    RiskDecision,
    RiskEngine,
    RiskSignals,
)


class TrialAction(StrEnum):
    FREE_SCAN = "free_scan"
    CHALLENGE = "challenge"
    PAYMENT_REQUIRED = "payment_required"
    BLOCK_REVIEW = "block_review"


@dataclass(frozen=True, slots=True)
class TrialRiskRequest:
    request_id: str
    user_id: UUID | None
    signals: RiskSignals

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id is required")
        if len(self.request_id) > 120:
            raise ValueError("request_id cannot exceed 120 characters")


@dataclass(frozen=True, slots=True)
class TrialDecision:
    action: TrialAction
    assessment: RiskAssessment


class RiskEventWriter(Protocol):
    async def record(
        self,
        *,
        request_id: str,
        user_id: UUID | None,
        assessment: RiskAssessment,
    ) -> None: ...


class SqlAlchemyRiskEventWriter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        request_id: str,
        user_id: UUID | None,
        assessment: RiskAssessment,
    ) -> None:
        for evidence in assessment.evidence:
            self._session.add(
                RiskEvent(
                    user_id=user_id,
                    request_id=request_id,
                    signal=evidence.signal,
                    weight=evidence.weight,
                    value_hash=evidence.value_hash,
                    metadata_json=dict(evidence.metadata),
                )
            )
        self._session.add(
            RiskEvent(
                user_id=user_id,
                request_id=request_id,
                signal="risk_decision",
                weight=assessment.score,
                metadata_json={"decision": assessment.decision.value},
            )
        )
        await self._session.commit()


class TrialRiskService:
    _ACTIONS = {
        RiskDecision.LOW: TrialAction.FREE_SCAN,
        RiskDecision.MEDIUM: TrialAction.CHALLENGE,
        RiskDecision.HIGH: TrialAction.PAYMENT_REQUIRED,
        RiskDecision.BLOCK: TrialAction.BLOCK_REVIEW,
    }

    def __init__(
        self,
        *,
        event_writer: RiskEventWriter,
        risk_engine: RiskEngine | None = None,
    ) -> None:
        self._event_writer = event_writer
        self._risk_engine = risk_engine or RiskEngine()

    async def evaluate(self, request: TrialRiskRequest) -> TrialDecision:
        assessment = self._risk_engine.assess(request.signals)
        decision = TrialDecision(
            action=self._ACTIONS[assessment.decision],
            assessment=assessment,
        )
        await self._event_writer.record(
            request_id=request.request_id,
            user_id=request.user_id,
            assessment=assessment,
        )
        return decision
