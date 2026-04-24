"""
Calendar provider registry.

Add a new provider in three steps:
  1. Create a subclass of CalendarProvider in this package.
  2. Import it below.
  3. Append an instance to `PROVIDERS`.

Everything else (tool schemas, tool dispatch map, per-provider lookups)
is derived from that list.
"""

from .base import CalendarProvider
from .google import GoogleProvider
from .microsoft import MicrosoftProvider


PROVIDERS: list[CalendarProvider] = [
    GoogleProvider(),
    MicrosoftProvider(),
]


PROVIDERS_BY_NAME: dict[str, CalendarProvider] = {p.name: p for p in PROVIDERS}


def get_provider(name: str) -> CalendarProvider:
    """Look up a provider by its canonical name (e.g. 'google')."""
    try:
        return PROVIDERS_BY_NAME[name]
    except KeyError:
        raise ValueError(f"Unknown calendar provider: {name!r}")


TOOL_DEFINITIONS: list[dict] = [
    schema for p in PROVIDERS for schema in p.TOOL_DEFINITIONS
]


TOOL_MAP: dict = {}
for _p in PROVIDERS:
    TOOL_MAP.update(_p.tool_map())


__all__ = [
    "CalendarProvider",
    "GoogleProvider",
    "MicrosoftProvider",
    "PROVIDERS",
    "PROVIDERS_BY_NAME",
    "TOOL_DEFINITIONS",
    "TOOL_MAP",
    "get_provider",
]
