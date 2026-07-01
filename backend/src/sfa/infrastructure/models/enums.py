from enum import Enum


class Position(str, Enum):
    GK = "GK"
    DC = "DC"
    LAT = "LAT"
    MC = "MC"
    MCO = "MCO"
    EXT = "EXT"
    DEL = "DEL"


class EventType(str, Enum):
    GOAL = "goal"
    GOAL_PENALTY = "goal_penalty"
    GOAL_SHOOTOUT = "goal_shootout"
    GOAL_SHOOTOUT_DECISIVE = "goal_shootout_decisive"
    MISSED_SHOOTOUT = "missed_shootout"
    MISSED_SHOOTOUT_DECISIVE = "missed_shootout_decisive"
    ASSIST = "assist"
    CORNER_ASSIST = "corner_assist"
    KEY_PASS = "key_pass"
    STATS = "stats"


class IngestionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
