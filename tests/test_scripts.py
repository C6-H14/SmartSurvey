import scripts.run_extraction


def test_run_extraction_exposes_main_function():
    assert callable(scripts.run_extraction.main)