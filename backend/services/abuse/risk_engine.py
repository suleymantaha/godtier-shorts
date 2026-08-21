from __future__ import annotations

import hashlib
import hmac
import ipaddress
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class RiskDecision(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class RiskSignals:
    clerk_bot_detected: bool = False
    clerk_human_verified: bool = False
    turnstile_valid: bool | None = None
    account_age_minutes: int | None = None
    signup_velocity_1h: int = 0
    render_velocity_1h: int = 0
    ip_prefix_hash: str | None = None
    ip_prefix_velocity_1h: int = 0
    known_trial_identity: bool = False
    disposable_email: bool = False
    blocked_email: bool = False
    source_fingerprint_hash: str | None = None
    source_fingerprint_uses_24h: int = 0

    def __post_init__(self) -> None:
        counters = (
            self.signup_velocity_1h,
            self.render_velocity_1h,
            self.ip_prefix_velocity_1h,
            self.source_fingerprint_uses_24h,
        )
        if any(value < 0 for value in counters):
            raise ValueError("Risk velocity values cannot be negative")
        if self.account_age_minutes is not None and self.account_age_minutes < 0:
            raise ValueError("Account age cannot be negative")
        for name, value in (
            ("ip_prefix_hash", self.ip_prefix_hash),
            ("source_fingerprint_hash", self.source_fingerprint_hash),
        ):
            if value is not None and (
                len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ValueError(f"{name} must be a lowercase SHA-256 hash")
        if self.ip_prefix_velocity_1h and self.ip_prefix_hash is None:
            raise ValueError("IP prefix velocity requires a hash")
        if self.source_fingerprint_uses_24h and self.source_fingerprint_hash is None:
            raise ValueError("Source fingerprint velocity requires a hash")


@dataclass(frozen=True, slots=True)
class RiskEvidence:
    signal: str
    weight: int
    value_hash: str | None = None
    metadata: Mapping[str, int | bool | str] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    score: int
    decision: RiskDecision
    evidence: tuple[RiskEvidence, ...]


def derive_ip_prefix_hash(ip_address: str, *, hmac_key: str) -> str:
    key = hmac_key.encode("utf-8")
    if not key:
        raise ValueError("IP prefix HMAC key is required")
    address = ipaddress.ip_address(ip_address)
    prefix_length = 24 if address.version == 4 else 56
    prefix = ipaddress.ip_network(f"{address}/{prefix_length}", strict=False)
    return hmac.new(key, prefix.with_prefixlen.encode("ascii"), hashlib.sha256).hexdigest()


class RiskEngine:
    MEDIUM_SCORE = 20
    HIGH_SCORE = 50
    BLOCK_SCORE = 90

    def assess(self, signals: RiskSignals) -> RiskAssessment:
        evidence: list[RiskEvidence] = []

        def add(
            signal: str,
            weight: int,
            *,
            value_hash: str | None = None,
            metadata: Mapping[str, int | bool | str] | None = None,
        ) -> None:
            evidence.append(
                RiskEvidence(
                    signal=signal,
                    weight=weight,
                    value_hash=value_hash,
                    metadata=MappingProxyType(dict(metadata or {})),
                )
            )

        if signals.clerk_bot_detected:
            add("clerk_bot", self.BLOCK_SCORE)
        if signals.blocked_email:
            add("blocked_email", self.BLOCK_SCORE)
        if signals.disposable_email:
            add("disposable_email", 30)
        if signals.clerk_human_verified:
            add("clerk_human", -20)
        if signals.turnstile_valid is False:
            add("turnstile_failed", 20)
        elif signals.turnstile_valid is True:
            add("turnstile_passed", -10)

        if signals.account_age_minutes is not None:
            if signals.account_age_minutes < 60:
                add("new_account", 15, metadata={"age_minutes": signals.account_age_minutes})
            elif signals.account_age_minutes < 1_440:
                add("young_account", 5, metadata={"age_minutes": signals.account_age_minutes})
            elif signals.account_age_minutes >= 10_080:
                add("established_account", -10)

        self._add_velocity(evidence, "signup_velocity", signals.signup_velocity_1h)
        self._add_velocity(evidence, "render_velocity", signals.render_velocity_1h)
        self._add_velocity(
            evidence,
            "ip_prefix_velocity",
            signals.ip_prefix_velocity_1h,
            value_hash=signals.ip_prefix_hash,
            high_threshold=10,
            medium_threshold=5,
            high_weight=20,
            medium_weight=10,
        )
        if signals.known_trial_identity:
            add("known_trial_identity", 50)
        self._add_velocity(
            evidence,
            "source_fingerprint_reuse",
            signals.source_fingerprint_uses_24h,
            value_hash=signals.source_fingerprint_hash,
            high_threshold=5,
            medium_threshold=3,
            high_weight=25,
            medium_weight=15,
        )

        raw_score = sum(item.weight for item in evidence)
        score = max(0, min(100, raw_score))
        explicit_block = signals.clerk_bot_detected or signals.blocked_email
        decision = self._decision(score, explicit_block=explicit_block)
        return RiskAssessment(score=score, decision=decision, evidence=tuple(evidence))

    @staticmethod
    def _add_velocity(
        evidence: list[RiskEvidence],
        signal: str,
        value: int,
        *,
        value_hash: str | None = None,
        high_threshold: int = 5,
        medium_threshold: int = 3,
        high_weight: int = 25,
        medium_weight: int = 15,
    ) -> None:
        if value >= high_threshold:
            weight = high_weight
        elif value >= medium_threshold:
            weight = medium_weight
        else:
            return
        evidence.append(
            RiskEvidence(
                signal=signal,
                weight=weight,
                value_hash=value_hash,
                metadata=MappingProxyType({"count": value}),
            )
        )

    def _decision(self, score: int, *, explicit_block: bool) -> RiskDecision:
        if explicit_block:
            return RiskDecision.BLOCK
        if score >= self.HIGH_SCORE:
            return RiskDecision.HIGH
        if score >= self.MEDIUM_SCORE:
            return RiskDecision.MEDIUM
        return RiskDecision.LOW
