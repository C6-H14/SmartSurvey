import keyring


SERVICE_NAME = "SmartSurvey"
API_KEY_USER = "llm_api_key"


class MissingCredentialError(RuntimeError):
    pass


class CredentialStore:
    def __init__(self, keyring_backend=None):
        self.keyring = keyring_backend or keyring

    def set_api_key(self, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("API key must not be empty.")
        self.keyring.set_password(SERVICE_NAME, API_KEY_USER, api_key.strip())

    def get_api_key(self) -> str:
        api_key = self.keyring.get_password(SERVICE_NAME, API_KEY_USER)
        if not api_key:
            raise MissingCredentialError("No SmartSurvey API key is stored in the OS keyring.")
        return api_key

    def clear_api_key(self) -> None:
        self.keyring.delete_password(SERVICE_NAME, API_KEY_USER)

    def has_api_key(self) -> bool:
        return bool(self.keyring.get_password(SERVICE_NAME, API_KEY_USER))
