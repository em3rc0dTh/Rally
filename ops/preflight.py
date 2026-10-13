"""Rally production CONFIGURATION preflight.

Reads exported environment variables, never prints secrets. Does not contact
DNS/ACME, PostgreSQL, provider accounts, devices, or customer systems.
This is a necessary static gate, NOT production acceptance.
"""
import os
import re
import sys


def validate(values: dict[str, str]) -> list[str]:
    problems: list[str] = []
    admin = values.get("RALLY_ADMIN_KEY", "").strip()
    password = values.get("POSTGRES_PASSWORD", "").strip()
    runtime_password = values.get("RALLY_APP_PASSWORD", "").strip()
    domain = values.get("RALLY_DOMAIN", "").strip().lower()
    email = values.get("ACME_EMAIL", "").strip().lower()

    if len(admin) < 32 or len(set(admin)) < 10 or admin.lower().startswith(
        ("change", "replace", "example", "integration-only")
    ):
        problems.append("RALLY_ADMIN_KEY must be a random-looking secret of at least 32 characters")
    if not re.fullmatch(r"[0-9a-fA-F]{32,}", password) or len(set(password)) < 10:
        problems.append("POSTGRES_PASSWORD must be at least 32 hexadecimal characters with high variability")
    if not re.fullmatch(r"[0-9a-fA-F]{32,}", runtime_password) or len(set(runtime_password)) < 10:
        problems.append("RALLY_APP_PASSWORD must be a separately generated hexadecimal secret of at least 32 characters")
    if password and password == runtime_password:
        problems.append("RALLY_APP_PASSWORD must differ from POSTGRES_PASSWORD")
    if (not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{1,251}[a-z0-9])", domain)
        or "." not in domain
        or ".." in domain
        or domain.endswith((".example", ".example.com", ".test", ".invalid", ".localhost"))
        or domain.startswith(("localhost", "127."))):
        problems.append("RALLY_DOMAIN must be an actual DNS hostname, not a placeholder")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or email.endswith(
        ("@example.com", "@example.org", "@example.net")
    ):
        problems.append("ACME_EMAIL must be an operator-controlled, non-example mailbox")

    if values.get("RALLY_ENV") not in (None, "", "production"):
        problems.append("RALLY_ENV must be production (or omitted; Compose enforces it)")

    # Do not require RALLY_DATABASE_URL here: production Compose derives it
    # from the independent PostgreSQL password at deployment time.
    if values.get("RALLY_DATABASE_URL"):
        from urllib.parse import urlsplit, unquote
        url = urlsplit(values["RALLY_DATABASE_URL"])
        if url.scheme not in {"postgres", "postgresql"} or not url.hostname:
            problems.append("RALLY_DATABASE_URL must target PostgreSQL")
        if url.username != "rally_app":
            problems.append("RALLY_DATABASE_URL must use the non-superuser rally_app role")
        if unquote(url.password or "") != runtime_password:
            problems.append("RALLY_DATABASE_URL password differs from RALLY_APP_PASSWORD")

    return problems


def main() -> int:
    errors = validate(dict(os.environ))
    if errors:
        for message in errors:
            print("BLOCKED: " + message, file=sys.stderr)
        print("No deployment attempted.", file=sys.stderr)
        return 2
    print("Static configuration checks passed. Network, migrations, providers, "
          "backups and business acceptance still require live verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
