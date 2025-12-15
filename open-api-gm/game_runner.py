"""
game_runner.py
--------------
Step-based wrapper around existing play.py logic.
Does NOT break CLI.
"""

class Game:
    def __init__(self, ui):
        # Import lazily to avoid circular imports
        import play

        self.ui = ui

        # Call into play.py setup logic
        self.context = play.create_game_context(ui)

        self.started = False

    def step(self, player_input: dict):
        """
        Advance the game by one logical step.
        Non-blocking. Safe for web.
        """
        import play

        if not self.started:
            self.started = True
            play.start_game(self.context)
            return

        play.game_step(self.context, player_input)

    def handle_input(self, player_input: dict, session=None):
        """
        Adapter for GameSession; forwards to step().
        """
        return self.step(player_input)
