"""
Project Domain Entitet.

Projekat je agregat koji grupiše taskove i timske članove.
U DDD terminologiji, Project je Aggregate Root za svoje taskove —
taskovi ne postoje van konteksta projekta.

Biznis pravila:
  - Projekat mora imati vlasnika (owner_id).
  - Arhoviran projekat ne može primati nove taskove.
  - Samo aktivni projekti mogu biti na hold-u i obrnuto.
"""
from dataclasses import dataclass, field
from uuid import UUID

from app.domain.models.base import Entity
from app.domain.models.value_objects import ProjectStatus


# Dozvoljene tranzicije statusa: ključ -> skup sledećih validnih statusa
_STATUS_TRANSITIONS: dict[ProjectStatus, set[ProjectStatus]] = {
    ProjectStatus.PLANNING:  {ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED},
    ProjectStatus.ACTIVE:    {ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED},
    ProjectStatus.ON_HOLD:   {ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED},
    ProjectStatus.COMPLETED: {ProjectStatus.ARCHIVED},
    ProjectStatus.ARCHIVED:  set(),  # Terminalni status
}


@dataclass
class Project(Entity):
    """
    Domenski entitet koji predstavlja projekat.

    Project je Aggregate Root — upravlja životnim ciklusom
    povezanih resursa (taskovi, članovi).
    """

    # --- Osnovna polja ---
    name: str = ""
    description: str = ""
    slug: str = ""  # URL-friendly identifikator, npr. "my-awesome-project"

    # --- Vlasništvo i tim ---
    owner_id: UUID = field(default_factory=lambda: UUID(int=0))
    # Set member UUID-ova — koristimo set za O(1) lookup
    member_ids: set[UUID] = field(default_factory=set)

    # --- Status i vidljivost ---
    status: ProjectStatus = field(default=ProjectStatus.PLANNING)
    is_public: bool = False

    # --- Biznis metode: Upravljanje statusom ---

    def transition_to(self, new_status: ProjectStatus) -> None:
        """
        Menja status projekta uz validaciju dozvoljenih tranzicija.

        Raises:
            ValueError: Ako tranzicija nije dozvoljena biznis pravilima.
        """
        allowed = _STATUS_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Nije moguće preći sa statusa '{self.status}' na '{new_status}'. "
                f"Dozvoljeno: {', '.join(str(s) for s in allowed) or 'ništa (terminalni status)'}."
            )
        self.status = new_status
        self.touch()

    def activate(self) -> None:
        """Aktivira projekat (iz PLANNING ili ON_HOLD)."""
        self.transition_to(ProjectStatus.ACTIVE)

    def put_on_hold(self) -> None:
        """Pauzira aktivan projekat."""
        self.transition_to(ProjectStatus.ON_HOLD)

    def complete(self) -> None:
        """Označava projekat kao završen."""
        self.transition_to(ProjectStatus.COMPLETED)

    def archive(self) -> None:
        """Arhivira projekat. Terminalna akcija."""
        self.transition_to(ProjectStatus.ARCHIVED)

    # --- Biznis metode: Upravljanje članovima ---

    def add_member(self, user_id: UUID) -> None:
        """
        Dodaje člana u projekat.

        Raises:
            ValueError: Ako je projekat arhiviran ili je korisnik već član.
        """
        if self.status == ProjectStatus.ARCHIVED:
            raise ValueError("Nije moguće dodavati članove arhiviranom projektu.")
        if user_id == self.owner_id:
            raise ValueError("Vlasnik projekta je automatski član — ne treba posebno dodavati.")
        if user_id in self.member_ids:
            raise ValueError(f"Korisnik {user_id!s:.8}... je već član projekta.")
        self.member_ids.add(user_id)
        self.touch()

    def remove_member(self, user_id: UUID) -> None:
        """
        Uklanja člana iz projekta.

        Raises:
            ValueError: Ako pokušavamo ukloniti vlasnika ili ne-člana.
        """
        if user_id == self.owner_id:
            raise ValueError("Vlasnik projekta ne može biti uklonjen. Prebacite vlasništvo prvo.")
        if user_id not in self.member_ids:
            raise ValueError(f"Korisnik {user_id!s:.8}... nije član projekta.")
        self.member_ids.discard(user_id)
        self.touch()

    def transfer_ownership(self, new_owner_id: UUID) -> None:
        """
        Prebacuje vlasništvo nad projektom na drugog korisnika.
        Stari vlasnik postaje regularni član.
        """
        if new_owner_id == self.owner_id:
            raise ValueError("Novi vlasnik mora biti drugačija osoba od trenutnog vlasnika.")
        # Novi vlasnik više nije regularni član
        self.member_ids.discard(new_owner_id)
        # Stari vlasnik postaje regularni član
        self.member_ids.add(self.owner_id)
        self.owner_id = new_owner_id
        self.touch()

    # --- Upiti (Query methods) ---

    def is_member(self, user_id: UUID) -> bool:
        """Proverava da li je korisnik član ili vlasnik projekta."""
        return user_id == self.owner_id or user_id in self.member_ids

    def can_accept_tasks(self) -> bool:
        """Biznis pravilo: samo aktivni projekti mogu dobijati nove taskove."""
        return self.status == ProjectStatus.ACTIVE

    @property
    def total_members(self) -> int:
        """Ukupan broj članova uključujući vlasnika."""
        return len(self.member_ids) + 1  # +1 za vlasnika

    def __repr__(self) -> str:
        return (
            f"Project(id={self.id!s:.8}..., "
            f"name='{self.name}', "
            f"status={self.status}, "
            f"members={self.total_members})"
        )