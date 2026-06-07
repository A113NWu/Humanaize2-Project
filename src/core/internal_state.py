class InternalState:

    def __init__(self):

        self.current_goal = None

        self.current_emotion = "neutral"

        self.last_reflection = ""

        self.energy = 1.0

        self.focus = 1.0

    def set_emotion(self, emotion):

        self.current_emotion = emotion

    def reflect(self, thought):

        self.last_reflection = thought