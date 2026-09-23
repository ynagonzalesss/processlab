import pytest
from pydantic import ValidationError

from processlab.schema import Process
from tests.conftest import make_step


def test_valid_step_builds():
    assert make_step().id == "s1"


@pytest.mark.parametrize("field,value", [
    ("input_type", "email"),
    ("consequence", "extreme"),
    ("reversibility", "maybe"),
    ("id", "Bad Id"),
])
def test_invalid_values_rejected(field, value):
    with pytest.raises(ValidationError):
        make_step(**{field: value})


def test_unknown_fields_rejected():
    # Protects against an LLM inventing fields later
    with pytest.raises(ValidationError):
        make_step(confidence=0.99)


def test_duplicate_ids_rejected():
    with pytest.raises(ValidationError, match="Duplicate"):
        Process(name="p", steps=[make_step(id="a"), make_step(id="a")])


def test_unknown_dependency_rejected():
    with pytest.raises(ValidationError, match="unknown steps"):
        Process(name="p", steps=[make_step(id="a", depends_on=["ghost"])])


def test_self_dependency_rejected():
    with pytest.raises(ValidationError, match="itself"):
        Process(name="p", steps=[make_step(id="a", depends_on=["a"])])


def test_cycle_rejected():
    with pytest.raises(ValidationError, match="cycle"):
        Process(name="p", steps=[
            make_step(id="a", depends_on=["c"]),
            make_step(id="b", depends_on=["a"]),
            make_step(id="c", depends_on=["b"]),
        ])


def test_empty_process_rejected():
    with pytest.raises(ValidationError):
        Process(name="p", steps=[])
