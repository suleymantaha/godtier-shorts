from __future__ import annotations

import ipaddress

import pytest

from backend.services.abuse.risk_engine import (
    RiskDecision,
    RiskEngine,
    RiskSignals,
    derive_ip_prefix_hash,
)


def test_verified_established_human_is_low_risk() -> None:
    assessment = RiskEngine().assess(
        RiskSignals(
            clerk_human_verified=True,
            turnstile_valid=True,
            account_age_minutes=10_080,
        )
    )

    assert assessment.decision is RiskDecision.LOW
    assert assessment.score == 0


def test_new_account_without_challenge_requires_extra_challenge() -> None:
    assessment = RiskEngine().assess(
        RiskSignals(account_age_minutes=15, turnstile_valid=False)
    )

    assert assessment.decision is RiskDecision.MEDIUM
    assert {item.signal for item in assessment.evidence} >= {
        "new_account",
        "turnstile_failed",
    }


def test_known_trial_identity_removes_another_free_scan() -> None:
    assessment = RiskEngine().assess(RiskSignals(known_trial_identity=True))

    assert assessment.decision is RiskDecision.HIGH


@pytest.mark.parametrize(
    "signals",
    [
        RiskSignals(clerk_bot_detected=True),
        RiskSignals(blocked_email=True),
    ],
)
def test_explicit_provider_block_signal_requires_review(signals: RiskSignals) -> None:
    assert RiskEngine().assess(signals).decision is RiskDecision.BLOCK


def test_velocity_and_repeated_source_signals_accumulate_without_using_ip_alone() -> None:
    ordinary_ip = RiskEngine().assess(
        RiskSignals(ip_prefix_hash="a" * 64, ip_prefix_velocity_1h=1)
    )
    coordinated = RiskEngine().assess(
        RiskSignals(
            signup_velocity_1h=5,
            render_velocity_1h=5,
            ip_prefix_hash="a" * 64,
            ip_prefix_velocity_1h=10,
            source_fingerprint_hash="b" * 64,
            source_fingerprint_uses_24h=5,
        )
    )

    assert ordinary_ip.decision is RiskDecision.LOW
    assert coordinated.decision is RiskDecision.HIGH
    assert all("192.168" not in str(item) for item in coordinated.evidence)


@pytest.mark.parametrize(
    ("raw_ip", "expected_network"),
    [
        ("203.0.113.77", "203.0.113.0/24"),
        ("2001:db8:1234:5678::1", "2001:db8:1234:5600::/56"),
    ],
)
def test_ip_prefix_hash_is_stable_and_does_not_expose_raw_ip(
    raw_ip: str, expected_network: str
) -> None:
    first = derive_ip_prefix_hash(raw_ip, hmac_key="test-only-key")
    same_prefix_ip = str(next(ipaddress.ip_network(expected_network).hosts()))
    second = derive_ip_prefix_hash(same_prefix_ip, hmac_key="test-only-key")

    assert first == second
    assert len(first) == 64
    assert raw_ip not in first


def test_ip_prefix_hash_requires_a_secret_key() -> None:
    with pytest.raises(ValueError, match="HMAC"):
        derive_ip_prefix_hash("203.0.113.10", hmac_key="")


@pytest.mark.parametrize(
    "signal_kwargs",
    [
        {"ip_prefix_velocity_1h": 5},
        {"source_fingerprint_uses_24h": 3},
    ],
)
def test_velocity_evidence_cannot_be_recorded_without_its_hash(
    signal_kwargs: dict[str, int],
) -> None:
    with pytest.raises(ValueError, match="requires a hash"):
        RiskSignals(**signal_kwargs)
