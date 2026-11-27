import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_default_secret() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(environment="production", debug=False)


def test_production_rejects_debug_mode() -> None:
    with pytest.raises(ValidationError, match="DEBUG"):
        Settings(
            environment="production",
            debug=True,
            secret_key="a-very-strong-production-secret-key-32chars!",
        )


def test_production_accepts_secure_config() -> None:
    settings = Settings(
        environment="production",
        debug=False,
        secret_key="a-very-strong-production-secret-key-32chars!",
    )
    assert settings.environment == "production"
