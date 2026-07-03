from streamlit.testing.v1 import AppTest


def test_app_shows_actionable_error_when_api_key_is_missing() -> None:
    app = AppTest.from_file("app.py").run()

    assert not app.exception
    assert app.error
    assert "OPENAI_API_KEY is required" in app.error[0].value
