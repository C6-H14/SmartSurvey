import json
import pytest

from core.credentials import CredentialStore, MissingCredentialError


class FakeKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


SERVICE = "SmartSurvey"
JSON_USER = "json_credentials"
LEGACY_USER = "llm_api_key"
DEFAULT_BASE = "https://njusehub.info/v1"
DEFAULT_MODEL = "deepseek-v4-flash"


def test_get_all_with_json_entry():
    store = CredentialStore(keyring_backend=FakeKeyring())

    store.save_all(api_key="sk-json", api_base="https://custom.url/v1", model_name="gpt-4")

    result = store.get_all()
    assert result["llm_api_key"] == "sk-json"
    assert result["llm_api_base"] == "https://custom.url/v1"
    assert result["llm_model_name"] == "gpt-4"


def test_get_all_migrates_legacy_key():
    store = CredentialStore(keyring_backend=FakeKeyring())

    store.keyring.set_password(SERVICE, LEGACY_USER, "sk-legacy")

    result = store.get_all()
    assert result["llm_api_key"] == "sk-legacy"
    assert result["llm_api_base"] == DEFAULT_BASE
    assert result["llm_model_name"] == DEFAULT_MODEL

    json_raw = store.keyring.get_password(SERVICE, JSON_USER)
    assert json_raw is not None
    migrated = json.loads(json_raw)
    assert migrated["llm_api_key"] == "sk-legacy"

    legacy_raw = store.keyring.get_password(SERVICE, LEGACY_USER)
    assert legacy_raw is None


def test_get_all_no_credentials_returns_defaults():
    store = CredentialStore(keyring_backend=FakeKeyring())

    result = store.get_all()
    assert result["llm_api_key"] == ""
    assert result["llm_api_base"] == DEFAULT_BASE
    assert result["llm_model_name"] == DEFAULT_MODEL


def test_save_all_writes_json():
    store = CredentialStore(keyring_backend=FakeKeyring())

    store.save_all(api_key="sk-save", api_base="https://example.com/v1", model_name="claude-3")

    json_raw = store.keyring.get_password(SERVICE, JSON_USER)
    assert json_raw is not None
    parsed = json.loads(json_raw)
    assert parsed["llm_api_key"] == "sk-save"
    assert parsed["llm_api_base"] == "https://example.com/v1"
    assert parsed["llm_model_name"] == "claude-3"


def test_clear_all_removes_both_entries():
    store = CredentialStore(keyring_backend=FakeKeyring())

    store.keyring.set_password(SERVICE, JSON_USER, '{"llm_api_key":"sk-clear","llm_api_base":"https://x.com/v1","llm_model_name":"m1"}')
    store.keyring.set_password(SERVICE, LEGACY_USER, "sk-legacy")

    assert store.has_credentials() is True

    store.clear_all()

    assert store.keyring.get_password(SERVICE, JSON_USER) is None
    assert store.keyring.get_password(SERVICE, LEGACY_USER) is None
    assert store.has_credentials() is False


def test_has_credentials_detects_json_entry():
    store = CredentialStore(keyring_backend=FakeKeyring())

    assert store.has_credentials() is False

    store.save_all(api_key="sk-has", api_base=DEFAULT_BASE, model_name=DEFAULT_MODEL)

    assert store.has_credentials() is True


def test_empty_api_key_raises_on_save():
    store = CredentialStore(keyring_backend=FakeKeyring())

    with pytest.raises(ValueError, match="API key must not be empty"):
        store.save_all(api_key="", api_base=DEFAULT_BASE, model_name=DEFAULT_MODEL)

    with pytest.raises(ValueError, match="API key must not be empty"):
        store.save_all(api_key="   ", api_base=DEFAULT_BASE, model_name=DEFAULT_MODEL)