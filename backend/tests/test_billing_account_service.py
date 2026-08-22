from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.db.models import PaymentStatus, SubscriptionStatus
from backend.services.billing.account_service import (
    AccountRecord,
    BillingAccountService,
    PaymentRecord,
    PlanRecord,
    SubscriptionRecord,
)


class FakeAccountRepository:
    def __init__(self, record: AccountRecord) -> None:
        self.record = record
        self.user_ids = []

    async def get_account(self, user_id):
        self.user_ids.append(user_id)
        return self.record


@pytest.mark.asyncio
async def test_account_snapshot_reports_period_usage_and_clamps_wallet_values() -> None:
    user_id = uuid4()
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    creator = PlanRecord(uuid4(), "creator", "Creator", 9_900, "TRY", 1_000, 60, 10, 2, 30)
    repository = FakeAccountRepository(
        AccountRecord(
            subscription=SubscriptionRecord(
                plan=creator,
                status=SubscriptionStatus.PAST_DUE,
                period_start=now,
                period_end=now,
                cancel_at_period_end=True,
                grace_until=now,
            ),
            plans=(creator,),
            payments=(PaymentRecord(uuid4(), 9_900, "TRY", PaymentStatus.SUCCEEDED, now),),
            source_seconds_used=7_200,
            compute_credits_used=1_200,
            wallet_available=-10,
            wallet_reserved=25,
        )
    )

    account = await BillingAccountService(repository).get_account(user_id, interval="monthly")

    assert repository.user_ids == [user_id]
    assert account.subscription is not None
    assert account.subscription.status is SubscriptionStatus.PAST_DUE
    assert account.subscription.interval == "monthly"
    assert account.source_seconds_used == 7_200
    assert account.source_seconds_per_job_limit == 3_600
    assert account.compute_credits_used == 1_200
    assert account.compute_credits_available == 0
    assert account.compute_credits_reserved == 25
    assert account.payments[0].status is PaymentStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_account_snapshot_supports_users_without_a_subscription() -> None:
    free = PlanRecord(uuid4(), "free", "Free", 0, "TRY", 0, 30, 3, 1, 7)
    account = await BillingAccountService(
        FakeAccountRepository(
            AccountRecord(
                subscription=None,
                plans=(free,),
                payments=(),
                source_seconds_used=0,
                compute_credits_used=0,
                wallet_available=0,
                wallet_reserved=0,
            )
        )
    ).get_account(uuid4())

    assert account.subscription is None
    assert account.plans == (free,)
    assert account.source_seconds_per_job_limit == 1_800
