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
    ASSIST = "assist"
    CORNER_ASSIST = "corner_assist"
    KEY_PASS = "key_pass"
    STATS = "stats"


class IngestionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
