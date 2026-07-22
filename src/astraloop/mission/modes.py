from enum import StrEnum


class MissionMode(StrEnum):
    PRELAUNCH = "PRELAUNCH"
    ASCENT = "ASCENT"
    COAST = "COAST"
    DESCENT = "DESCENT"
    LANDING = "LANDING"
    LANDED = "LANDED"
    ABORT = "ABORT"


LEGAL_TRANSITIONS = {
    MissionMode.PRELAUNCH: frozenset((MissionMode.ASCENT, MissionMode.ABORT)),
    MissionMode.ASCENT: frozenset((MissionMode.COAST, MissionMode.ABORT)),
    MissionMode.COAST: frozenset((MissionMode.DESCENT, MissionMode.ABORT)),
    MissionMode.DESCENT: frozenset((MissionMode.LANDING, MissionMode.ABORT)),
    MissionMode.LANDING: frozenset((MissionMode.LANDED, MissionMode.ABORT)),
    MissionMode.LANDED: frozenset(),
    MissionMode.ABORT: frozenset(),
}

TERMINAL_MODES = frozenset((MissionMode.LANDED, MissionMode.ABORT))
