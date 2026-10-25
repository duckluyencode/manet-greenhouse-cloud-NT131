import pytest

TEST_API_KEY = "test-key"


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    """Mỗi test có API key và file SQLite riêng, không đụng results.db thật."""
    monkeypatch.setenv("CAAR_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("CAAR_DB_PATH", str(tmp_path / "test.db"))
