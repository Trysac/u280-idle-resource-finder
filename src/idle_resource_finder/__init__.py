"""Find idle cloud resources in a provider-neutral JSON inventory.

Public API:
- :class:`Thresholds`
- :class:`Resource`
- :class:`Finding`
- :class:`Report`
- :class:`IdleError`
- :func:`load_inventory`
- :func:`find_idle`
- :func:`render`
"""

from __future__ import annotations

import logging

from .errors import IdleError
from .inventory import load_inventory
from .models import Finding, Report, Resource, Thresholds
from .render import render
from .rules import find_idle

__all__ = [
    "Finding",
    "IdleError",
    "Report",
    "Resource",
    "Thresholds",
    "__version__",
    "find_idle",
    "load_inventory",
    "render",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
