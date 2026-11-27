from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def no_env_file(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make Settings() read only os.environ, never the developer's repo-root .env."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_missing_site_origin_fails_fast(monkeypatch: pytest.MonkeyPatch, no_env_file: None) -> None:
    monkeypatch.delenv("SITE_ORIGIN", raising=False)
    with pytest.raises(ValidationError, match="site_origin"):
        Settings()


def test_app_refuses_to_start_without_site_origin(
    monkeypatch: pytest.MonkeyPatch, no_env_file: None
) -> None:
    monkeypatch.delenv("SITE_ORIGIN", raising=False)
    with pytest.raises(ValidationError, match="site_origin"):
        create_app()


def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch, no_env_file: None) -> None:
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("SITE_ORIGIN", "HTTP://LocalHost:3000/")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, http://127.0.0.1:3000")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = Settings()

    assert settings.site_origin == "http://localhost:3000"
    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:3000"]
    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize(
    "origin",
    [
        "localhost:3000",  # no scheme
        "ftp://example.com",
        "https://example.com/app",  # path
        "https://example.com?x=1",
        "https://user:pw@example.com",
        "https://example.com:99999",
        "null",
        "",
    ],
)
def test_invalid_site_origin_is_rejected(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, site_origin=origin)


def test_invalid_cors_origin_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, site_origin="http://a.test", cors_origins=["not an origin"])


def test_production_requires_https_site_origin() -> None:
    with pytest.raises(ValidationError, match="https"):
        Settings(_env_file=None, env="production", site_origin="http://rg.example.com")


def test_unknown_env_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="staging", site_origin="https://rg.example.com")  # type: ignore[arg-type]


def test_unset_env_fails_closed(monkeypatch: pytest.MonkeyPatch, no_env_file: None) -> None:
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("SITE_ORIGIN", "https://rg.example.com")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")

    settings = Settings()

    assert settings.env == "production"
    assert settings.allowed_origins == {"https://rg.example.com"}
    assert not settings.cors_enabled


def test_unset_env_still_requires_https(monkeypatch: pytest.MonkeyPatch, no_env_file: None) -> None:
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("SITE_ORIGIN", "http://rg.example.com")

    with pytest.raises(ValidationError, match="https"):
        Settings()


@pytest.mark.parametrize("env", ["ci", "production"])
def test_cors_origins_ignored_outside_local(env: str) -> None:
    settings = Settings(
        _env_file=None,
        env=env,  # type: ignore[arg-type]
        site_origin="https://rg.example.com",
        cors_origins=["http://localhost:3000"],
    )

    assert settings.allowed_origins == {"https://rg.example.com"}
    assert not settings.cors_enabled


def test_cors_origins_only_widen_allowed_origins_in_local() -> None:
    local = Settings(
        _env_file=None,
        env="local",
        site_origin="http://localhost:8000",
        cors_origins=["http://localhost:3000"],
    )
    prod = Settings(
        _env_file=None,
        env="production",
        site_origin="https://rg.example.com",
        cors_origins=["http://localhost:3000"],
    )

    assert local.allowed_origins == {"http://localhost:8000", "http://localhost:3000"}
    assert local.cors_enabled
    assert prod.allowed_origins == {"https://rg.example.com"}
    assert not prod.cors_enabled


def test_login_throttle_defaults() -> None:
    settings = Settings(_env_file=None, site_origin="https://rg.example.com")

    assert settings.login_max_failures_per_account == 5
    assert settings.login_max_failures_per_ip == 30
    assert settings.login_throttle_window_seconds == 900
    assert settings.trusted_proxies == []


def test_trusted_proxies_parse_from_a_comma_separated_list(
    monkeypatch: pytest.MonkeyPatch, no_env_file: None
) -> None:
    monkeypatch.setenv("SITE_ORIGIN", "https://rg.example.com")
    monkeypatch.setenv("TRUSTED_PROXIES", "172.18.0.0/16, 10.0.0.5")

    assert Settings().trusted_proxies == ["172.18.0.0/16", "10.0.0.5/32"]


@pytest.mark.parametrize("value", ["*", "caddy", "10.0.0.0/33"])
def test_trusted_proxies_reject_anything_but_addresses(value: str) -> None:
    with pytest.raises(ValidationError, match="IP address or CIDR"):
        Settings(_env_file=None, site_origin="https://rg.example.com", trusted_proxies=[value])
