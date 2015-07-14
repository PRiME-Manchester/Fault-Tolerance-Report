import pytest

from mock import Mock

from network_tester.errors import NT_ERR, NetworkTesterError


def test_from_int():
    # Special case: empty
    assert NT_ERR.from_int(0) == set()

    # Should produce values
    integer = (NT_ERR.STILL_RUNNING +
               NT_ERR.DMA)
    assert NT_ERR.from_int(integer) == set([NT_ERR.STILL_RUNNING, NT_ERR.DMA])

    # Should fail with more bits than are recognised
    with pytest.raises(ValueError):
        NT_ERR.from_int(0xFFFFFFFF)


def test_is_deadline():
    assert not NT_ERR.STILL_RUNNING.is_deadline
    assert not NT_ERR.MALLOC.is_deadline
    assert not NT_ERR.DMA.is_deadline
    assert not NT_ERR.UNKNOWN_COMMAND.is_deadline
    assert not NT_ERR.BAD_ARGUMENTS.is_deadline

    assert NT_ERR.DEADLINE_MISSED.is_deadline
    assert NT_ERR.MOST_DEADLINES_MISSED.is_deadline


def test_exception():
    # The exception should be able to unpack the set of errors from a set of
    # results into a sensible message

    mock_results = Mock()
    mock_results.errors = set([NT_ERR.DMA])

    # Single error should have a full error name in
    err = NetworkTesterError(mock_results)
    assert err.results is mock_results
    assert "NT_ERR_DMA" in str(err)

    # Multiple errors should also be listed
    mock_results.errors = set([NT_ERR.DMA, NT_ERR.DEADLINE_MISSED])
    err = NetworkTesterError(mock_results)
    assert err.results is mock_results
    assert "DMA" in str(err)
    assert "DEADLINE_MISSED" in str(err)
