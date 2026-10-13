"""Configuration checks without storing or revealing credentials."""
from ops.preflight import validate

def good():
    return {
        "RALLY_ADMIN_KEY": "0123456789abcdef"*4,
        "POSTGRES_PASSWORD": "abcdef0123456789"*4,
        "RALLY_APP_PASSWORD": "fedcba9876543210"*4,
        "RALLY_DOMAIN": "rally.customer-operations.com",
        "ACME_EMAIL": "security@customer-operations.com",
        "RALLY_ENV": "production",
    }

def test_preflight_accepts_well_formed_external_config():
    assert validate(good()) == []

def test_preflight_rejects_examples_and_weak_secrets():
    config = good()
    config.update({
        "RALLY_ADMIN_KEY": "replace-me",
        "POSTGRES_PASSWORD": "password123",
        "RALLY_DOMAIN": "rally.example.com",
        "ACME_EMAIL": "ops@example.com",
    })
    failures = validate(config)
    assert len(failures) >= 4
    assert not any("abcdef0123456789" in item for item in failures)

def test_preflight_rejects_wrong_database_password():
    config = good()
    config["RALLY_DATABASE_URL"] = "postgresql://rally_app:wrong@postgres:5432/rally"
    assert any("password differs" in e for e in validate(config))


def test_rejects_same_superuser_and_runtime_password():
    config = good()
    config["RALLY_APP_PASSWORD"] = config["POSTGRES_PASSWORD"]
    assert any("must differ" in error for error in validate(config))

def test_rejects_runtime_superuser_connection():
    config = good()
    config["RALLY_DATABASE_URL"] = "postgresql://rally:abcdef0123456789@postgres:5432/rally"
    assert any("non-superuser" in error for error in validate(config))
