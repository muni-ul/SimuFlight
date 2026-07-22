from enum import StrEnum


class MissionMode(StrEnum):
    PRELAUNCH = "PRELAUNCH"
    ASCENT = "ASCENT"
    COAST = "COAST"
    DESCENT = "DESCENT"
    LANDING = "LANDING"
    LANDED = "LANDED"
    ABORT = "ABORT"
