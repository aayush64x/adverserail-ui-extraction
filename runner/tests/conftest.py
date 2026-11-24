import sys
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER))
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(scope="session")
def fixture_data(tmp_path_factory):
    import make_fixture
    return make_fixture.make(tmp_path_factory.mktemp("data") / "fixture_data")
