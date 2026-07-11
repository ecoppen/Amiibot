from dataclasses import dataclass, field
from enum import Enum, auto


class RunStatus(Enum):
    SUCCESS = auto()
    PARTIAL = auto()
    FAILURE = auto()


class FailureCategory(Enum):
    CONFIG = "config"
    DATABASE = "database"
    NETWORK = "network"
    PARSER = "parser"
    UNEXPECTED = "unexpected"


@dataclass
class RunResult:
    status: RunStatus
    exit_code: int
    stockists_attempted: int = 0
    stockists_succeeded: int = 0
    stockists_failed: int = 0
    notifications_sent: int = 0
    failure_category: FailureCategory | None = None
    errors: list[str] = field(default_factory=list)
