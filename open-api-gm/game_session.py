
from typing import Dict, Any, List

class GameSession:
    def __init__(self, game):
        self.game = game
        self.events: List[Dict[str, Any]] = []

    def emit(self, event: Dict[str, Any]):
        self.events.append(event)

    def step(self, player_input: Dict[str, Any]):
        self.events = []
        self.game.handle_input(player_input, self)
        return self.events
