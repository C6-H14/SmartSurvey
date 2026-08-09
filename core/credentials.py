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
    """Store LLM credentials with a resilient, layered persistence strategy.

    Primary backend is the OS keyring. Because public headless hosts (e.g.
    Streamlit Community Cloud) have no D-Bus daemon, *every* keyring call is
    wrapped in a try/except: when keyring is unavailable we transparently
    degrade to per-session in-memory storage. This guarantees
    ``has_credentials()``/``get_all()`` always work and never raise a
    ``NoKeyringError`` (which would red-screen the app).
    """

    def __init__(self, keyring_backend=None):
        self.keyring = keyring_backend or keyring
        # Fallback store used when the OS keyring is unavailable. A fresh
        # CredentialStore is instantiated per Streamlit rerun in main.py, so
        # per-instance memory already gives per-user/session isolation.
        self._memory: dict = {}
        # Set True on first keyring failure so subsequent calls short-circuit.
        self._keyring_failed = False

    def _session_store(self) -> dict:
        """Return the dict that should back this store's current session.

        When running under Streamlit, persist into ``st.session_state`` so
        credentials survive within one user's session across reruns; otherwise
        (CLI, tests) fall back to the per-instance dict.
        """
        try:
            import streamlit as st

            if "credential_store" not in st.session_state:
                st.session_state.credential_store = {}
            return st.session_state.credential_store
        except Exception:
            return self._memory

    def save_all(self, api_key: str, api_base: str, model_name: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("API key must not be empty.")
        credentials = {
            "llm_api_key": api_key.strip(),
            "llm_api_base": api_base,
            "llm_model_name": model_name,
        }
        payload = json.dumps(credentials)
        if self._keyring_failed:
            self._session_store()[JSON_USER] = payload
            return
        try:
            self.keyring.set_password(SERVICE_NAME, JSON_USER, payload)
        except Exception:
            self._keyring_failed = True
            self._session_store()[JSON_USER] = payload

    def get_all(self) -> dict:
        if self._keyring_failed:
            return self._read_session()
        try:
            json_raw = self.keyring.get_password(SERVICE_NAME, JSON_USER)
        except Exception:
            self._keyring_failed = True
            return self._read_session()

        if json_raw:
            return json.loads(json_raw)

        try:
            legacy_key = self.keyring.get_password(SERVICE_NAME, LEGACY_USER)
        except Exception:
            self._keyring_failed = True
            return self._read_session()

        if legacy_key is None:
            # Fall back to memory once keyring reports no credentials.
            session = self._session_store()
            remembered = session.get(JSON_USER)
            if remembered is not None:
                return json.loads(remembered)
            return {
                "llm_api_key": "",
                "llm_api_base": DEFAULT_API_BASE,
                "llm_model_name": DEFAULT_MODEL_NAME,
            }

        credentials = {
            "llm_api_key": legacy_key,
            "llm_api_base": DEFAULT_API_BASE,
            "llm_model_name": DEFAULT_MODEL_NAME,
        }
        try:
            self.keyring.set_password(
                SERVICE_NAME, JSON_USER, json.dumps(credentials)
            )
            self.keyring.delete_password(SERVICE_NAME, LEGACY_USER)
        except Exception:
            self._keyring_failed = True
            self._session_store()[JSON_USER] = json.dumps(credentials)
        return credentials

    def _read_session(self) -> dict:
        session = self._session_store()
        remembered = session.get(JSON_USER)
        if remembered is not None:
            return json.loads(remembered)
        return {
            "llm_api_key": "",
            "llm_api_base": DEFAULT_API_BASE,
            "llm_model_name": DEFAULT_MODEL_NAME,
        }

    def has_credentials(self) -> bool:
        if self._keyring_failed:
            return JSON_USER in self._session_store()
        try:
            real = bool(
                self.keyring.get_password(SERVICE_NAME, JSON_USER)
                or self.keyring.get_password(SERVICE_NAME, LEGACY_USER)
            )
        except Exception:
            self._keyring_failed = True
            return JSON_USER in self._session_store()
        if real:
            return True
        return JSON_USER in self._session_store()

    def clear_all(self) -> None:
        if self._keyring_failed:
            self._session_store().pop(JSON_USER, None)
            self._session_store().pop(LEGACY_USER, None)
            return
        try:
            self.keyring.delete_password(SERVICE_NAME, JSON_USER)
            self.keyring.delete_password(SERVICE_NAME, LEGACY_USER)
        except Exception:
            self._keyring_failed = True
            self._session_store().pop(JSON_USER, None)
            self._session_store().pop(LEGACY_USER, None)