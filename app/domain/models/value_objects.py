"""
Value Objects za Task Management domenu.

U DDD-u, Value Objects su nepromenljivi objekti koji su definisani
isključivo svojom vrednošću — nemaju identitet (ID).
Savršeni su za statuse, prioritete, uloge i slične koncepte.

Koristimo StrEnum (Python 3.11+) kako bi bili i string-kompatibilni
(direktno serializable u JSON) i type-safe.
"""
from enum import StrEnum, auto


class UserRole(StrEnum):
    """
    Uloga korisnika u sistemu (globalni nivo).

    ADMIN  — pun pristup svemu, upravljanje korisnicima.
    MEMBER — standardni korisnik, može raditi na projektima.
    VIEWER — read-only pristup (npr. klijenti, gosti).
    """
    ADMIN = auto()    # => "admin"
    MEMBER = auto()   # => "member"
    VIEWER = auto()   # => "viewer"


class ProjectStatus(StrEnum):
    """
    Životni ciklus projekta.

    PLANNING   — projekat je kreiran, još nije aktivan.
    ACTIVE     — projekat je u toku.
    ON_HOLD    — privremeno pauziran.
    COMPLETED  — svi zadaci završeni.
    ARCHIVED   — arhiviran, samo za čitanje.
    """
    PLANNING = auto()   # => "planning"
    ACTIVE = auto()     # => "active"
    ON_HOLD = auto()    # => "on_hold"
    COMPLETED = auto()  # => "completed"
    ARCHIVED = auto()   # => "archived"


class TaskStatus(StrEnum):
    """
    Tok životnog ciklusa taska (Kanban stil).

    BACKLOG     — evidentiran, nije ušao u sprint.
    TODO        — ušao u sprint, nije počet.
    IN_PROGRESS — aktivno se radi.
    IN_REVIEW   — čeka code review / QA.
    DONE        — završen i verifikovan.
    CANCELLED   — otkazan, neće biti urađen.
    """
    BACKLOG = auto()       # => "backlog"
    TODO = auto()          # => "todo"
    IN_PROGRESS = auto()   # => "in_progress"
    IN_REVIEW = auto()     # => "in_review"
    DONE = auto()          # => "done"
    CANCELLED = auto()     # => "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Vraća True ako je status konačan (ne može se menjati dalje)."""
        return self in (TaskStatus.DONE, TaskStatus.CANCELLED)

    @property
    def is_active(self) -> bool:
        """Vraća True ako se aktivno radi na tasku."""
        return self == TaskStatus.IN_PROGRESS


class TaskPriority(StrEnum):
    """
    Prioritet taska.

    CRITICAL — blokira produkciju / release.
    HIGH     — mora u ovaj sprint.
    MEDIUM   — standardni prioritet.
    LOW      — nice-to-have, radi se kad ima vremena.
    """
    CRITICAL = auto()  # => "critical"
    HIGH = auto()      # => "high"
    MEDIUM = auto()    # => "medium"
    LOW = auto()       # => "low"

    @property
    def sort_order(self) -> int:
        """Numerička vrednost za sortiranje (manji broj = veći prioritet)."""
        _order = {
            TaskPriority.CRITICAL: 1,
            TaskPriority.HIGH: 2,
            TaskPriority.MEDIUM: 3,
            TaskPriority.LOW: 4,
        }
        return _order[self]