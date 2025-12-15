
from ui.provider import UIProvider

class WebProvider(UIProvider):
    def __init__(self, session):
        self.session = session

    def scene(self, text, data=None):
        self.session.emit({"type": "scene", "text": text, "data": data})

    def narration(self, text, data=None):
        self.session.emit({"type": "narration", "text": text, "data": data})

    def loot(self, text, data=None):
        self.session.emit({"type": "loot", "text": text, "data": data})

    def system(self, text, data=None):
        self.session.emit({"type": "system", "text": text, "data": data})

    def error(self, text, data=None):
        self.session.emit({"type": "error", "text": text, "data": data})

    def choice(self, prompt, options, data=None):
        self.session.emit({
            "type": "choice",
            "prompt": prompt,
            "options": options
        })
        return None

    def text_input(self, prompt, data=None):
        self.session.emit({
            "type": "input",
            "prompt": prompt
        })
        return None
