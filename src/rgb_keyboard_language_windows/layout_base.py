"""Base class for keyboard layout detection (abstraction for cross-platform support)."""

from abc import ABC, abstractmethod


class LayoutDetector(ABC):
    """
    Abstract base class for detecting current keyboard layout.

    This abstraction allows for future macOS implementation.
    """

    @abstractmethod
    def get_current_layout(self) -> str | None:
        """
        Get current keyboard layout as BCP-47 language code.

        Returns:
            BCP-47 language code (e.g., "en-US", "ru-RU") or None if detection fails
        """
        pass

