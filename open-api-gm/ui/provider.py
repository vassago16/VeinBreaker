from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class UIProvider(ABC):
    """
    UI abstraction. The game emits structured events. The provider renders them.
    Providers may be CLI, Discord, Web, etc.
    """

    @abstractmethod
    def scene(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        pass

    @abstractmethod
    def narration(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        pass

    @abstractmethod
    def loot(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        pass

    @abstractmethod
    def system(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        pass

    @abstractmethod
    def error(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        pass

    @abstractmethod
    def choice(
        self,
        prompt: str,
        options: List[str],
        data: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Returns the 0-based index of the selected option.
        """
        pass

    @abstractmethod
    def text_input(
        self,
        prompt: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Returns raw string input (used rarely; prefer choice()).
        """
        pass
