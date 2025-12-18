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
        self.is_web = not ui.is_blocking

        # Call into play.py setup logic
        self.context = play.create_game_context(
            ui,
            skip_character_creation=self.is_web
        )

        self.started = False

    def step(self, player_input: dict):
        """
        Advance the game by one logical step.
        Non-blocking. Safe for web.
        """
        import play

        # Web/UI is step-driven: do not auto-run `start_game()` on first request.
        # The client decides whether to `action: start` or enter character creation.
        if not self.started:
            self.started = True

        play.game_step(self.context, player_input)

    def handle_input(self, player_input: dict, session=None):
        """
        Adapter for GameSession; forwards to step().
        """
        return self.step(player_input)
