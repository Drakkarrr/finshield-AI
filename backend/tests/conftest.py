"""Shared test setup. APP_ENV must be set before any app module is imported."""
import os

os.environ["APP_ENV"] = "test"

import pytest  # noqa: E402

from app.database import IS_SQLITE, create_test_schema  # noqa: E402

create_test_schema()


def pytest_collection_modifyitems(config, items):
    if not IS_SQLITE:
        return
    skip = pytest.mark.skip(reason="needs TEST_DATABASE_URL=postgresql://...")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip)
