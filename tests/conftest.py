import pytest


@pytest.fixture
def sample_page_texts():
    return {
        1: "Abstract This paper studies spatial anomaly detection. Introduction Safety matters.",
        2: "The method uses a vision model. The limitation is lighting sensitivity.",
    }