from datetime import date
from pathlib import Path

from emporio.config import Settings


def test_empty_optional_values_from_example_env_use_defaults(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=\n"
        "MODEL=openai:gpt-4o-mini\n"
        "EMBEDDING_MODEL=text-embedding-3-small\n"
        "REFERENCE_DATE=\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.openai_api_key is None
    assert settings.reference_date is None
    assert settings.model == "openai:gpt-4o-mini"


def test_overrides_by_field_name_are_applied(tmp_path: Path) -> None:
    # get_settings(**overrides) uses Python field names, not env aliases; they
    # must not be silently ignored (this regressed a REFERENCE_DATE demo).
    settings = Settings(_env_file=tmp_path / "missing.env", reference_date=date(2026, 2, 20))

    assert settings.reference_date == date(2026, 2, 20)
