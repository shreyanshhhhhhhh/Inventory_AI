from sqlalchemy import func, select

from app.models import Business, User
from app.repositories.businesses import get_business
from app.services.auth import AuthError, login, signup


def test_signup_hashes_password_and_creates_one_business(db) -> None:
    result = signup(
        db,
        full_name="Ada Owner",
        email="ada@example.com",
        password="correct-horse-1",
        business_name="North Shop",
    )
    user = db.scalar(select(User).where(User.email == "ada@example.com"))
    assert user is not None
    assert user.password_hash != "correct-horse-1"
    assert "correct-horse-1" not in user.password_hash
    assert user.password_hash.startswith("$argon2id$")
    assert user.role == "owner"
    assert user.business_id == result.user.business_id

    business = get_business(db, user.business_id or "")
    assert business is not None
    assert business.name == "North Shop"
    assert business.currency_code == "USD"
    assert business.onboarding_completed_at is None
    assert db.scalar(select(func.count()).select_from(Business)) == 1


def test_login_rejects_wrong_password(db) -> None:
    signup(
        db,
        full_name="Ada Owner",
        email="ada@example.com",
        password="correct-horse-1",
        business_name="North Shop",
    )
    try:
        login(db, email="ada@example.com", password="not-the-password")
    except AuthError as exc:
        assert exc.status_code == 401
        assert exc.message == "Email or password is incorrect."
    else:
        raise AssertionError("wrong password was accepted")


def test_scoped_business_query_does_not_return_the_other_tenant(db) -> None:
    first = signup(
        db,
        full_name="Ada Owner",
        email="a@example.com",
        password="correct-horse-1",
        business_name="Shop A",
    )
    second = signup(
        db,
        full_name="Bea Owner",
        email="b@example.com",
        password="correct-horse-1",
        business_name="Shop B",
    )
    visible = get_business(db, first.user.business_id)
    assert visible is not None
    assert visible.id == first.user.business_id
    assert visible.name == "Shop A"
    assert visible.id != second.user.business_id
