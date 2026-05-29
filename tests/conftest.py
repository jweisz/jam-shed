"""
Test configuration for jam-shed.
"""
import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment."""
    # Future: Mock MIDI devices, audio, etc.
    pass
