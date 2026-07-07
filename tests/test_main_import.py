import main


def test_main_exposes_app_entrypoint():
    assert callable(main.run_app)
