"""
User Domain Entitet.

Predstavlja registrovanog korisnika sistema. Sadrži:
  - Autentifikacione podatke (email, hashed_password).
  - Ulogu u sistemu (UserRole).
  - Biznis logiku vezanu za korisnika (aktivacija, deaktivacija, promena uloge).

NAPOMENA: hashed_password je ovde string — hashing se radi u
          infrastructure/security sloju, ne u domenu.
"""
from dataclasses import dataclass, field

from app.domain.models.base import Entity
from app.domain.models.value_objects import UserRole


@dataclass
class User(Entity):
    """
    Domenski entitet koji predstavlja korisnika.

    Biznis invarijanta: korisnik može biti aktivan ili neaktivan.
    Neaktivan korisnik se ne može prijaviti niti vršiti akcije.
    """

    # --- Identifikaciona polja ---
    email: str = ""
    username: str = ""
    full_name: str = ""

    # --- Autentifikacija ---
    # Čuvamo HASH, nikad plain text password
    hashed_password: str = ""

    # --- Uloga i status ---
    role: UserRole = field(default=UserRole.MEMBER)
    is_active: bool = True
    is_verified: bool = False  # Email verifikacija

    # --- Biznis metode ---

    def deactivate(self) -> None:
        """
        Deaktivira korisnika.
        Deaktiviran korisnik ne može da se prijavi.
        """
        if not self.is_active:
            raise ValueError(f"Korisnik '{self.username}' je već deaktiviran.")
        self.is_active = False
        self.touch()

    def activate(self) -> None:
        """Reaktivira prethodno deaktiviranog korisnika."""
        if self.is_active:
            raise ValueError(f"Korisnik '{self.username}' je već aktivan.")
        self.is_active = True
        self.touch()

    def verify_email(self) -> None:
        """Označava da je korisnik verifikovao email adresu."""
        if self.is_verified:
            raise ValueError("Email je već verifikovan.")
        self.is_verified = True
        self.touch()

    def promote_to_admin(self) -> None:
        """Promovišuje korisnika u admina."""
        if self.role == UserRole.ADMIN:
            raise ValueError(f"Korisnik '{self.username}' je već admin.")
        self.role = UserRole.ADMIN
        self.touch()

    def change_role(self, new_role: UserRole) -> None:
        """Menja ulogu korisnika uz logovanje promene."""
        if self.role == new_role:
            raise ValueError(f"Korisnik već ima ulogu '{new_role}'.")
        self.role = new_role
        self.touch()

    def can_manage_projects(self) -> bool:
        """Biznis pravilo: samo ADMIN i MEMBER mogu kreirati/menjati projekte."""
        return self.role in (UserRole.ADMIN, UserRole.MEMBER) and self.is_active

    def is_admin(self) -> bool:
        """Helper za proveru admin uloge."""
        return self.role == UserRole.ADMIN and self.is_active

    def __repr__(self) -> str:
        return (
            f"User(id={self.id!s:.8}..., "
            f"username='{self.username}', "
            f"role={self.role}, "
            f"active={self.is_active})"
        )