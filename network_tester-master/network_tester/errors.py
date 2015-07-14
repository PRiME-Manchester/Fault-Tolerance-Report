"""The errors which can occur during an experiment."""

from enum import IntEnum


class NT_ERR(IntEnum):
    """The set of error flag bits which may be set by a network tester
    application running on SpiNNaker."""

    """The application has not yet terminated."""
    STILL_RUNNING = 1 << 0

    """Failed to allocate memory."""
    MALLOC = 1 << 1

    """A DMA transfer failed."""
    DMA = 1 << 2

    """An unrecognised command was encountered."""
    UNKNOWN_COMMAND = 1 << 3

    """A command was passed invalid arguments."""
    BAD_ARGUMENTS = 1 << 4

    """A realtime deadline was missed."""
    DEADLINE_MISSED = 1 << 5

    """More than half of the realtime deadlines were missed during at least one
    phase of the experiment."""
    MOST_DEADLINES_MISSED = 1 << 6

    @property
    def is_deadline(self):
        """True iff the flag indicates a deadline was missed."""
        return self in (NT_ERR.DEADLINE_MISSED, NT_ERR.MOST_DEADLINES_MISSED)

    @classmethod
    def from_int(cls, integer):
        """Unpack an integer into a list of NT_ERR values."""
        out = set()
        for err in cls:
            if err & integer:
                out.add(err)
                integer &= ~err

        if integer != 0:
            raise ValueError("Unknown error bits {}".format(bin(integer)))

        return out


class NetworkTesterError(Exception):
    """Indicates that one or more errors occurred during an experimental
    run.

    Attributes
    ----------
    results : :py:class:`network_tester.results.Results`
        The experimental results recorded. These results should be treated with
        caution.
    """

    def __init__(self, results):
        self.results = results

        errors = self.results.errors

        if len(errors) == 1:
            message = "An error occurred during traffic simulation: "
            message += "NT_ERR_{}".format(list(errors)[0].name)
        else:
            message = "Errors occurred during traffic simulation: "
            message += "NT_ERR_{{{}}}".format("|".join(
                err.name for err in errors))

        super(NetworkTesterError, self).__init__(message)
