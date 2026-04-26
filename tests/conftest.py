from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def workspace_tmp() -> Path:
    """pytest 標準 workspace_tmp を避け、ワークスペース内の一時領域を使う。"""

    root = Path.cwd() / "test_tmp_workspace" / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)
