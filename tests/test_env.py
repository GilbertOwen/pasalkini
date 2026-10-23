"""Settings from .env: read into the environment, never over a variable already set."""

import os

from pasalkini.env import load_env


def test_a_dotenv_file_fills_what_the_environment_lacks(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text('# comment\nGEMINI_API_KEY="abc"\nexport OTHER=1\nSET_ALREADY=file\n\n')
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OTHER", raising=False)
    monkeypatch.setenv("SET_ALREADY", "shell")
    assert load_env(path) == ["GEMINI_API_KEY", "OTHER"]
    assert os.environ["GEMINI_API_KEY"] == "abc" and os.environ["SET_ALREADY"] == "shell"
    assert load_env(tmp_path / "missing") == []
