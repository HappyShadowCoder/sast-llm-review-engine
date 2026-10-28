import pytest
from src.sast_runner import SASTRunner
from src.reviewer import StructuredReviewer
from src.publisher import VCSPublisher


@pytest.fixture
def sast_runner():
    return SASTRunner()


@pytest.fixture
def reviewer():
    return StructuredReviewer()


@pytest.fixture
def publisher():
    return VCSPublisher()
