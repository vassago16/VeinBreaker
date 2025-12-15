from __future__ import annotations

from typing import Any, Dict, List, Optional
from ui.provider import UIProvider


class CLIProvider(UIProvider):
    def scene(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        print()
        print(text)
        print()

    def narration(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        print(text)

    def loot(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        print()
        print(text)
        print()

    def system(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        print(text)

    def error(self, text: str, data: Optional[Dict[str, Any]] = None) -> None:
        print(f"[ERROR] {text}")

    def choice(self, prompt: str, options: List[str], data: Optional[Dict[str, Any]] = None) -> int:
        print()
        if prompt:
            print(prompt)
        for i, opt in enumerate(options, start=1):
            print(f"{i}. {opt}")

        while True:
            raw = input("> ").strip()
            try:
                sel = int(raw)
                if 1 <= sel <= len(options):
                    return sel - 1
            except ValueError:
                pass
            self.error(f"Enter a number from 1 to {len(options)}.")

    def text_input(self, prompt: str, data: Optional[Dict[str, Any]] = None) -> str:
        print()
        return input(f"{prompt}\n> ").strip()

    def clear(self, target: str = "narration") -> None:
        # Simple CLI clear: push content off screen
        print("\n" * 40)
