"""
Email address blocklist. The file is read on every lookup, so that changes take effect without a
restart.
"""

import logging
from fnmatch import fnmatchcase

PATH = "/etc/gatekeeper/email-blocklist.txt"

logger = logging.getLogger(__name__)


def _read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return [line for line in map(str.strip, f) if line and not line.startswith("#")]


def match(email, path=None):
    """
    Return the blocklist line that blocks the given email address, or None if it is not blocked.
    A blocklist that is absent or cannot be read blocks nothing.
    """
    path = path or PATH
    try:
        lines = _read_lines(path)
    except FileNotFoundError:
        logger.info("No email blocklist at %s", path)
        return None
    except OSError as e:
        logger.warning("Could not read email blocklist: %s", e)
        return None

    email = email.lower()
    for line in lines:
        # Lines starting with '!' are exceptions. The first matching line decides.
        negated = line.startswith("!")
        pattern = line.removeprefix("!").strip() if negated else line
        if fnmatchcase(email, pattern.lower()):
            return None if negated else line
    return None
