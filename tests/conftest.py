import json
from pathlib import Path

import pytest

from processlab.engine import load_config
from processlab.schema import Process, Step

ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def config():
    return load_config()


@pytest.fixture(scope="session")
def guest_process():
    data = json.loads((ROOT / "examples" / "guest_onboarding.json").read_text())
    return Process.model_validate(data)


def make_step(**overrides) -> Step:
    """A safe, boring default step; override only what a test cares about."""
    base = dict(
        id="s1", name="Step", actor="Admin",
        input_type="structured", rule_clarity="clear", reversibility="reversible",
        consequence="low", domains=[], volume="medium", exception_rate="low",
    )
    base.update(overrides)
    return Step(**base)
