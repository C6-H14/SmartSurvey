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


def test_store_set_get_clear_key():
    store = CredentialStore(keyring_backend=FakeKeyring())

    store.set_api_key("sk-test")

    assert store.has_api_key() is True
    assert store.get_api_key() == "sk-test"

    store.clear_api_key()

    assert store.has_api_key() is False


def test_missing_key_raises_clear_error():
    store = CredentialStore(keyring_backend=FakeKeyring())

    with pytest.raises(MissingCredentialError, match="No SmartSurvey API key"):
        store.get_api_key()
