"""
Task Domain Entitet.

Task je centralni entitet sistema — razlog postojanja aplikacije.
Sadrži kompleksnu biznis logiku: status tranzicije, dodelu, prioritizaciju,
rokove i hijerarhiju (parent-child tasks).

Biznis pravila:
  - Task mora pripadati projektu.
  - Task u terminalnom statusu (DONE/CANCELLED) ne može biti menjam.
  - Rok (due_date) ne može biti u prošlosti pri kreiranju.
  - Samo jedan assignee po tasku (za jednostavnost; proširivo).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from app.domain.models.base import Entity, _utcnow
from app.domain.models.value_objects import TaskPriority, TaskStatus


# Dozvoljene tranzicije statusa taska
_STATUS_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.BACKLOG:      {TaskStatus.TODO, TaskStatus.CANCELLED},
    TaskStatus.TODO:         {TaskStatus.IN_PROGRESS, TaskStatus.BACKLOG, TaskStatus.CANCELLED},
    TaskStatus.IN_PROGRESS:  {TaskStatus.IN_REVIEW, TaskStatus.TODO, TaskStatus.CANCELLED},
    TaskStatus.IN_REVIEW:    {TaskStatus.DONE, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
    TaskStatus.DONE:         set(),        # Terminalni status
    TaskStatus.CANCELLED:    {TaskStatus.BACKLOG},  # Može se "reopenovat" u backlog
}


@dataclass
class Task(Entity):
    """
    Domenski entitet koji predstavlja jedan zadatak.

    Čuva sve relevantne informacije o tasku i enkapsulira
    biznis logiku vezanu za njegov životni ciklus.
    """

    # --- Osnovna polja ---
    title: str = ""
    description: str = ""

    # --- Relacije (čuvamo samo ID-jeve, ne objekte — DDD princip) ---
    project_id: UUID = field(default_factory=lambda: UUID(int=0))
    reporter_id: UUID = field(default_factory=lambda: UUID(int=0))  # Ko je kreirao task
    assignee_id: UUID | None = None  # Ko radi na tasku (opciono)

    # --- Value Objects ---
    status: TaskStatus = field(default=TaskStatus.BACKLOG)
    priority: TaskPriority = field(default=TaskPriority.MEDIUM)

    # --- Vremenski okvir ---
    due_date: datetime | None = None
    started_at: datetime | None = None   # Kada je prešao u IN_PROGRESS
    completed_at: datetime | None = None  # Kada je prešao u DONE

    # --- Hijerarhija (opciona) ---
    parent_task_id: UUID | None = None  # Subtask podrška

    # --- Tagovi za filtriranje ---
    tags: list[str] = field(default_factory=list)

    # --- Biznis metode: Status tranzicije ---

    def transition_to(self, new_status: TaskStatus) -> None:
        """
        Menja status taska uz validaciju i side-effects.

        Side-effects:
          - Prelaz u IN_PROGRESS setuje started_at.
          - Prelaz u DONE setuje completed_at.

        Raises:
            ValueError: Ako je tranzicija zabranjena ili je task u terminalnom statusu.
        """
        if self.status.is_terminal and new_status != TaskStatus.BACKLOG:
            raise ValueError(
                f"Task u statusu '{self.status}' je terminalan i ne može biti menjam "
                f"(osim vraćanja u backlog za CANCELLED)."
            )

        allowed = _STATUS_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Tranzicija '{self.status}' → '{new_status}' nije dozvoljena. "
                f"Dozvoljeno: {', '.join(str(s) for s in allowed) or 'ništa'}."
            )

        # Side-effects pri specifičnim tranzicijama
        if new_status == TaskStatus.IN_PROGRESS and self.started_at is None:
            self.started_at = _utcnow()
        elif new_status == TaskStatus.DONE:
            self.completed_at = _utcnow()
        elif new_status == TaskStatus.BACKLOG:
            # "Reopen" — resetujemo completion timestamp
            self.completed_at = None

        self.status = new_status
        self.touch()

    def move_to_todo(self) -> None:
        """Prelaz u TODO — task je ušao u sprint, spreman za rad."""
        self.transition_to(TaskStatus.TODO)

    def start(self) -> None:
        """
        Prelaz u IN_PROGRESS — počinje aktivni rad na tasku.
        Ako je task u BACKLOG, automatski prolazi kroz TODO.
        """
        if self.status == TaskStatus.BACKLOG:
            self.transition_to(TaskStatus.TODO)
        self.transition_to(TaskStatus.IN_PROGRESS)

    def submit_for_review(self) -> None:
        """Prelaz u IN_REVIEW — čeka pregled."""
        self.transition_to(TaskStatus.IN_REVIEW)

    def complete(self) -> None:
        """Prelaz u DONE — task je završen i verifikovan."""
        self.transition_to(TaskStatus.DONE)

    def cancel(self) -> None:
        """Otkazuje task."""
        self.transition_to(TaskStatus.CANCELLED)

    def reopen(self) -> None:
        """Vraća otkazani task u backlog."""
        if self.status != TaskStatus.CANCELLED:
            raise ValueError("Samo CANCELLED taskovi mogu biti reopened.")
        self.transition_to(TaskStatus.BACKLOG)

    # --- Biznis metode: Dodela ---

    def assign_to(self, user_id: UUID) -> None:
        """
        Dodeljuje task korisniku.

        Raises:
            ValueError: Ako je task u terminalnom statusu.
        """
        if self.status.is_terminal:
            raise ValueError(f"Ne može se dodeliti task u statusu '{self.status}'.")
        self.assignee_id = user_id
        self.touch()

    def unassign(self) -> None:
        """Uklanja dodelu taska."""
        if self.assignee_id is None:
            raise ValueError("Task nije dodeljen nikome.")
        self.assignee_id = None
        self.touch()

    # --- Biznis metode: Prioritet i rokovi ---

    def change_priority(self, new_priority: TaskPriority) -> None:
        """Menja prioritet taska."""
        if self.status.is_terminal:
            raise ValueError(f"Ne može se menjati prioritet taska u statusu '{self.status}'.")
        if self.priority == new_priority:
            raise ValueError(f"Task već ima prioritet '{new_priority}'.")
        self.priority = new_priority
        self.touch()

    def set_due_date(self, due_date: datetime) -> None:
        """
        Postavlja rok za task.

        Raises:
            ValueError: Ako je rok u prošlosti.
        """
        if self.status.is_terminal:
            raise ValueError("Ne može se menjati rok završenog/otkazanog taska.")
        now = datetime.now(timezone.utc)
        if due_date.tzinfo is None:
            raise ValueError("due_date mora biti timezone-aware datetime.")
        if due_date <= now:
            raise ValueError(f"Rok ne može biti u prošlosti. Zadato: {due_date.isoformat()}")
        self.due_date = due_date
        self.touch()

    def clear_due_date(self) -> None:
        """Uklanja rok sa taska."""
        self.due_date = None
        self.touch()

    # --- Biznis metode: Tagovi ---

    def add_tag(self, tag: str) -> None:
        """Dodaje tag tasku (case-insensitive, bez duplikata)."""
        normalized = tag.strip().lower()
        if not normalized:
            raise ValueError("Tag ne može biti prazan string.")
        if normalized in self.tags:
            raise ValueError(f"Tag '{normalized}' već postoji na ovom tasku.")
        self.tags.append(normalized)
        self.touch()

    def remove_tag(self, tag: str) -> None:
        """Uklanja tag sa taska."""
        normalized = tag.strip().lower()
        if normalized not in self.tags:
            raise ValueError(f"Tag '{normalized}' ne postoji na ovom tasku.")
        self.tags.remove(normalized)
        self.touch()

    # --- Upiti (Query methods) ---

    @property
    def is_overdue(self) -> bool:
        """Vraća True ako je rok prošao a task nije završen."""
        if self.due_date is None or self.status.is_terminal:
            return False
        return datetime.now(timezone.utc) > self.due_date

    @property
    def is_assigned(self) -> bool:
        """Vraća True ako je task dodeljen nekome."""
        return self.assignee_id is not None

    @property
    def is_subtask(self) -> bool:
        """Vraća True ako je ovo subtask (ima parent)."""
        return self.parent_task_id is not None

    def __repr__(self) -> str:
        return (
            f"Task(id={self.id!s:.8}..., "
            f"title='{self.title[:30]}', "
            f"status={self.status}, "
            f"priority={self.priority})"
        )