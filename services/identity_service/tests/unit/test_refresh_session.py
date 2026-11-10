from datetime import UTC, datetime, timedelta
from uuid import uuid4

from identity_service.domain.entities import RefreshSession

NOW = datetime(2030, 1, 1, tzinfo=UTC)


def make_session(*, expires_at: datetime) -> RefreshSession:
    return RefreshSession(
        user_id=uuid4(),
        token_hash="a" * 64,
        expires_at=expires_at,
    )


def test_new_unexpired_session_is_active() -> None:
    session = make_session(expires_at=NOW + timedelta(days=1))

    assert session.is_active(NOW)


def test_session_is_inactive_at_expiration_time() -> None:
    session = make_session(expires_at=NOW)

    assert not session.is_active(NOW)


def test_revoked_session_is_inactive() -> None:
    session = make_session(expires_at=NOW + timedelta(days=1))

    session.revoke()

    assert session.revoked_at is not None
    assert session.replaced_by_session_id is None
    assert not session.is_active(NOW)


def test_revoke_is_idempotent() -> None:
    session = make_session(expires_at=NOW + timedelta(days=1))

    session.revoke()
    first_revoked_at = session.revoked_at
    session.revoke()

    assert first_revoked_at is not None
    assert session.revoked_at == first_revoked_at


def test_replace_with_revokes_old_session_and_links_replacement() -> None:
    old_session = make_session(expires_at=NOW + timedelta(days=1))
    replacement_id = uuid4()

    old_session.replace_with(replacement_id)

    assert old_session.revoked_at is not None
    assert old_session.replaced_by_session_id == replacement_id
    assert not old_session.is_active(NOW)


def test_replacement_stays_in_the_same_family() -> None:
    old_session = make_session(expires_at=NOW + timedelta(days=1))

    replacement = RefreshSession(
        user_id=old_session.user_id,
        family_id=old_session.family_id,
        token_hash="b" * 64,
        expires_at=NOW + timedelta(days=30),
    )
    old_session.replace_with(replacement.id)

    assert replacement.family_id == old_session.family_id
    assert old_session.replaced_by_session_id == replacement.id
