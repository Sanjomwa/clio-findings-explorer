import re
from typing import get_args

from app.schemas import RegimeState

_PRE_TRANSITION = re.compile(r"pre_transition:([A-Z_]+)")
_STATES = set(get_args(RegimeState))


def pre_transition_target(classification_reason: str | None) -> str | None:
    """The state named by `pre_transition:<STATE>`, or None if absent or not a known state."""
    match = _PRE_TRANSITION.search(classification_reason or "")
    if match and match.group(1) in _STATES:
        return match.group(1)
    return None
