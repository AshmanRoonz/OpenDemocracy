"""Abstract base class for platform connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from opendemocracy.models import Opinion


class BaseConnector(ABC):
    """Interface that all platform connectors must implement."""

    @abstractmethod
    def fetch_opinions(
        self,
        topic: str,
        *,
        limit: int = 100,
    ) -> list[Opinion]:
        """Fetch opinions about *topic*, returning at most *limit* results.

        Implementations must anonymize all data before returning.
        """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Human-readable name of the platform (e.g. 'Reddit')."""
