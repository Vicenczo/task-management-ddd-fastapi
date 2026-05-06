"""
Base klase za sve domenskih entitete.

U DDD-u, entiteti imaju identitet (ID) koji ih razlikuje čak i kada
su sva ostala polja ista. Value Objects nemaju sopstveni identitet
- definisani su isključivo svojom vrednošću.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    """Vraća trenutno UTC vreme sa timezone info. Uvek koristiti ovu funkciju."""
    return datetime.now(timezone.utc)


@dataclass
class Entity:
    """
    Bazna klasa za sve domenske entitete.

    Svaki entitet ima:
      - id: Globalno jedinstven identifikator (UUID v4).
      - created_at / updated_at: Audit trail timestamps.

    eq=False: Dva entiteta su ista AKO I SAMO AKO imaju isti ID,
    bez obzira na vrednosti ostalih polja (osnovno DDD pravilo).
    """

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def touch(self) -> None:
        """Ažurira updated_at na trenutno vreme. Poziva se pri svakoj izmeni."""
        self.updated_at = _utcnow()