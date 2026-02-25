"""Server-side identity registry.

Stores the mapping from anonymous participant IDs to public keys.  This is
the **only** identity-related data the server holds — no biometric
templates, no names, no personal information.

In production this would be backed by a database with audit logging.  The
in-memory implementation here defines the interface.
"""

from __future__ import annotations

from opendemocracy.models import EnrollmentRecord


class IdentityRegistry:
    """In-memory registry of enrolled participants.

    Maps ``anonymous_id → EnrollmentRecord`` and maintains an index from
    ``public_key → anonymous_id`` for duplicate detection.
    """

    def __init__(self) -> None:
        self._records: dict[str, EnrollmentRecord] = {}
        self._pubkey_index: dict[str, str] = {}

    # -- mutations --------------------------------------------------------

    def register(self, record: EnrollmentRecord) -> None:
        """Add a new enrollment record.

        Raises ``RuntimeError`` if the anonymous ID or public key is
        already registered.
        """
        if record.anonymous_id in self._records:
            raise RuntimeError(
                f"Anonymous ID {record.anonymous_id!r} already registered"
            )
        if record.public_key in self._pubkey_index:
            raise RuntimeError("Public key already registered to another participant")

        self._records[record.anonymous_id] = record
        self._pubkey_index[record.public_key] = record.anonymous_id

    def revoke(self, anonymous_id: str) -> bool:
        """Revoke an enrollment.  Returns ``True`` if the ID was found."""
        record = self._records.get(anonymous_id)
        if record is None:
            return False
        record.revoked = True
        return True

    # -- queries ----------------------------------------------------------

    def lookup(self, anonymous_id: str) -> EnrollmentRecord | None:
        """Retrieve an enrollment record by anonymous ID."""
        return self._records.get(anonymous_id)

    def lookup_by_public_key(self, public_key: str) -> EnrollmentRecord | None:
        """Retrieve an enrollment record by public key."""
        anon_id = self._pubkey_index.get(public_key)
        if anon_id is None:
            return None
        return self._records.get(anon_id)

    def is_enrolled(self, anonymous_id: str) -> bool:
        """Check if a participant is enrolled and not revoked."""
        record = self._records.get(anonymous_id)
        return record is not None and not record.revoked

    @property
    def count(self) -> int:
        """Number of enrolled participants (including revoked)."""
        return len(self._records)

    @property
    def active_count(self) -> int:
        """Number of active (non-revoked) participants."""
        return sum(1 for r in self._records.values() if not r.revoked)
