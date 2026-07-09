import json

import keyring


SERVICE_NAME = "SmartSurvey"
JSON_USER = "json_credentials"
LEGACY_USER = "llm_api_key"
DEFAULT_API_BASE = "https://njusehub.info/v1"
DEFAULT_MODEL_NAME = "deepseek-v4-flash"


class MissingCredentialError(RuntimeError):
    pass


class CredentialStore:
    def __init__(self, keyring_backend=None):
        self.keyring = keyring_backend or keyring

    def save_all(self, api_key: str, api_base: str, model_name: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("API key must not be empty.")
        credentials = {
            "llm_api_key": api_key.strip(),
            "llm_api_base": api_base,
            "llm_model_name": model_name,
        }
        self.keyring.set_password(SERVICE_NAME, JSON_USER, json.dumps(credentials))

    def get_all(self) -> dict:
        json_raw = self.keyring.get_password(SERVICE_NAME, JSON_USER)
        if json_raw:
            return json.loads(json_raw)

        legacy_key = self.keyring.get_password(SERVICE_NAME, LEGACY_USER)
        if legacy_key:
            credentials = {
                "llm_api_key": legacy_key,
                "llm_api_base": DEFAULT_API_BASE,
                "llm_model_name": DEFAULT_MODEL_NAME,
            }
            self.keyring.set_password(
                SERVICE_NAME, JSON_USER, json.dumps(credentials)
            )
            self.keyring.delete_password(SERVICE_NAME, LEGACY_USER)
            return credentials

        return {
            "llm_api_key": "",
            "llm_api_base": DEFAULT_API_BASE,
            "llm_model_name": DEFAULT_MODEL_NAME,
        }

    def has_credentials(self) -> bool:
        return bool(
            self.keyring.get_password(SERVICE_NAME, JSON_USER)
            or self.keyring.get_password(SERVICE_NAME, LEGACY_USER)
        )

    def clear_all(self) -> None:
        self.keyring.delete_password(SERVICE_NAME, JSON_USER)
        self.keyring.delete_password(SERVICE_NAME, LEGACY_USER)