import pytest
from streamlit.testing.v1 import AppTest


def test_app_shows_actionable_error_when_api_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A whitespace-only key overrides any developer .env and is treated as missing,
    # so the test is deterministic regardless of the local environment.
    monkeypatch.setenv("OPENAI_API_KEY", " ")
    app = AppTest.from_file("app.py").run()

    assert not app.exception
    assert app.error
    assert "OPENAI_API_KEY is required" in app.error[0].value
