import upgrade_copilot


def test_package_imports() -> None:
    assert upgrade_copilot.__version__ == "0.1.0.dev0"
