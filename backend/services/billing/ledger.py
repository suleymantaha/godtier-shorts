from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import CreditLedgerEntry, CreditWallet, Job, JobStatus, LedgerKind
from backend.db.session import get_session_factory


class LedgerError(RuntimeError):
    pass


class InvalidLedgerAmount(LedgerError):
    pass


class IdempotencyConflict(LedgerError):
    pass


class InsufficientCredits(LedgerError):
    pass


class JobNotFound(LedgerError):
    pass


class InvalidJobState(LedgerError):
    pass


class NoActiveReservation(LedgerError):
    pass


class AdjustmentWouldOverdraw(LedgerError):
    pass


def _positive_amount(amount: int) -> int:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise InvalidLedgerAmount("amount pozitif bir tam sayi olmali")
    return amount


def _settlement_amount(amount: int) -> int:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise InvalidLedgerAmount("actual_amount negatif olmayan bir tam sayi olmali")
    return amount


def _key(idempotency_key: str) -> str:
    normalized = idempotency_key.strip()
    if not normalized:
        raise IdempotencyConflict("idempotency_key bos olamaz")
    return normalized


async def _claim_entry(
    session: AsyncSession,
    *,
    user_id: UUID,
    kind: LedgerKind,
    amount: int,
    idempotency_key: str,
    job_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    metadata_json = dict(metadata or {})
    inserted_id = await session.scalar(
        insert(CreditLedgerEntry)
        .values(
            user_id=user_id,
            kind=kind,
            amount=amount,
            job_id=job_id,
            idempotency_key=idempotency_key,
            metadata_json=metadata_json,
        )
        .on_conflict_do_nothing(index_elements=[CreditLedgerEntry.idempotency_key])
        .returning(CreditLedgerEntry.id)
    )
    if inserted_id is not None:
        return True

    existing = await session.scalar(
        select(CreditLedgerEntry).where(CreditLedgerEntry.idempotency_key == idempotency_key)
    )
    if existing is None:
        raise IdempotencyConflict("idempotency kaydi okunamadi")
    if (
        existing.user_id != user_id
        or existing.kind is not kind
        or existing.amount != amount
        or existing.job_id != job_id
        or existing.metadata_json != metadata_json
    ):
        raise IdempotencyConflict("idempotency_key farkli bir islem icin kullanilmis")
    return False


async def _lock_wallet(session: AsyncSession, user_id: UUID) -> CreditWallet:
    await session.execute(
        insert(CreditWallet)
        .values(user_id=user_id)
        .on_conflict_do_nothing(index_elements=[CreditWallet.user_id])
    )
    wallet = await session.scalar(
        select(CreditWallet).where(CreditWallet.user_id == user_id).with_for_update()
    )
    if wallet is None:
        raise LedgerError("kredi cuzdanina erisilemedi")
    return wallet


async def _lock_job(session: AsyncSession, user_id: UUID, job_id: UUID) -> Job:
    job = await session.scalar(
        select(Job).where(Job.id == job_id, Job.user_id == user_id).with_for_update()
    )
    if job is None:
        raise JobNotFound("job bulunamadi")
    return job


async def grant(
    user_id: UUID,
    amount: int,
    idempotency_key: str,
    metadata: dict[str, Any],
) -> None:
    amount = _positive_amount(amount)
    idempotency_key = _key(idempotency_key)
    factory = get_session_factory()
    async with factory() as session, session.begin():
        await grant_in_session(session, user_id, amount, idempotency_key, metadata)


async def grant_in_session(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    idempotency_key: str,
    metadata: dict[str, Any],
) -> bool:
    amount = _positive_amount(amount)
    idempotency_key = _key(idempotency_key)
    claimed = await _claim_entry(
        session,
        user_id=user_id,
        kind=LedgerKind.GRANT,
        amount=amount,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )
    if not claimed:
        return False
    wallet = await _lock_wallet(session, user_id)
    wallet.available += amount
    return True


async def adjust_in_session(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    idempotency_key: str,
    metadata: dict[str, Any],
) -> int:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount == 0:
        raise InvalidLedgerAmount("adjustment amount sifir olmayan bir tam sayi olmali")
    idempotency_key = _key(idempotency_key)
    claimed = await _claim_entry(
        session,
        user_id=user_id,
        kind=LedgerKind.ADJUSTMENT,
        amount=amount,
        idempotency_key=idempotency_key,
        metadata=metadata,
    )
    wallet = await _lock_wallet(session, user_id)
    if claimed:
        if wallet.available + amount < 0:
            raise AdjustmentWouldOverdraw("kredi duzeltmesi bakiyeyi negatif yapamaz")
        wallet.available += amount
    return wallet.available


async def reserve_in_session(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    job_id: UUID,
    idempotency_key: str,
) -> bool:
    amount = _positive_amount(amount)
    idempotency_key = _key(idempotency_key)
    claimed = await _claim_entry(
        session,
        user_id=user_id,
        kind=LedgerKind.RESERVE,
        amount=amount,
        job_id=job_id,
        idempotency_key=idempotency_key,
    )
    if not claimed:
        return False
    wallet = await _lock_wallet(session, user_id)
    job = await _lock_job(session, user_id, job_id)
    if job.reserved_credits or job.settled_credits:
        raise InvalidJobState("job icin daha once kredi ayrilmis veya harcanmis")
    if wallet.available < amount:
        raise InsufficientCredits("yetersiz kullanilabilir kredi")
    wallet.available -= amount
    wallet.reserved += amount
    job.reserved_credits = amount
    return True


async def reserve(
    user_id: UUID,
    amount: int,
    job_id: UUID,
    idempotency_key: str,
) -> None:
    amount = _positive_amount(amount)
    idempotency_key = _key(idempotency_key)
    factory = get_session_factory()
    async with factory() as session, session.begin():
        await reserve_in_session(session, user_id, amount, job_id, idempotency_key)


async def settle(
    user_id: UUID,
    job_id: UUID,
    actual_amount: int,
    idempotency_key: str,
) -> None:
    actual_amount = _settlement_amount(actual_amount)
    idempotency_key = _key(idempotency_key)
    factory = get_session_factory()
    async with factory() as session, session.begin():
        claimed = await _claim_entry(
            session,
            user_id=user_id,
            kind=LedgerKind.SETTLE,
            amount=actual_amount,
            job_id=job_id,
            idempotency_key=idempotency_key,
        )
        if not claimed:
            return
        wallet = await _lock_wallet(session, user_id)
        job = await _lock_job(session, user_id, job_id)
        reserved_amount = job.reserved_credits
        if reserved_amount <= 0:
            raise NoActiveReservation("job icin aktif kredi rezervasyonu yok")

        extra_charge = max(0, actual_amount - reserved_amount)
        if wallet.available < extra_charge:
            raise InsufficientCredits("settlement icin ek kredi yetersiz")
        wallet.available -= extra_charge
        wallet.available += max(0, reserved_amount - actual_amount)
        wallet.reserved -= reserved_amount
        job.reserved_credits = 0
        job.settled_credits = actual_amount


async def release(
    user_id: UUID,
    job_id: UUID,
    idempotency_key: str,
) -> None:
    idempotency_key = _key(idempotency_key)
    factory = get_session_factory()
    async with factory() as session, session.begin():
        await release_in_session(session, user_id, job_id, idempotency_key)


async def release_in_session(
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    idempotency_key: str,
) -> bool:
    idempotency_key = _key(idempotency_key)
    wallet = await _lock_wallet(session, user_id)
    job = await _lock_job(session, user_id, job_id)
    reserved_amount = job.reserved_credits
    if reserved_amount <= 0:
        existing = await session.scalar(
            select(CreditLedgerEntry).where(
                CreditLedgerEntry.idempotency_key == idempotency_key
            )
        )
        if (
            existing is not None
            and existing.user_id == user_id
            and existing.kind is LedgerKind.RELEASE
            and existing.job_id == job_id
        ):
            return False
        raise NoActiveReservation("job icin aktif kredi rezervasyonu yok")
    if job.status not in {JobStatus.ERROR, JobStatus.CANCELLED}:
        raise InvalidJobState("yalniz failed veya cancelled job rezervasyonu release edilebilir")
    claimed = await _claim_entry(
        session,
        user_id=user_id,
        kind=LedgerKind.RELEASE,
        amount=reserved_amount,
        job_id=job_id,
        idempotency_key=idempotency_key,
    )
    if not claimed:
        return False
    wallet.available += reserved_amount
    wallet.reserved -= reserved_amount
    job.reserved_credits = 0
    return True
