from core.agent import create_extraction_fn


class FakeCredentialStore:
    def get_api_key(self):
        return "sk-fake-test-key"


def test_create_extraction_fn_returns_callable():
    fn = create_extraction_fn(credential_store=FakeCredentialStore())
    assert callable(fn)
    # The returned function should accept a prompt string and return a string
    result = fn("Return the word test.")
    assert isinstance(result, str)