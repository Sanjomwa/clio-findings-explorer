import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if "tests/unit/" in item.nodeid.replace("\\", "/"):
            item.add_marker(pytest.mark.unit)
