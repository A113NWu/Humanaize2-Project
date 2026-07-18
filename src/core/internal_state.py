class InternalState:

    def __init__(self):

        self.current_goal = None

        self.last_reflection = ""

        self.energy = 1.0

        self.focus = 1.0
        
        self._init_emotion_engine()

    def _init_emotion_engine(self):
        """初始化情感引擎"""
        try:
            from tools.emotion_engine import emotion_engine
            self.emotion_engine = emotion_engine
        except ImportError:
            self.emotion_engine = None
            self.current_emotion = "neutral"

    def set_emotion(self, emotion, intensity=0.5):
        """设置情绪"""
        if self.emotion_engine:
            self.emotion_engine.set_emotion(emotion, intensity)
        else:
            self.current_emotion = emotion

    def get_emotion(self):
        """获取当前情绪"""
        if self.emotion_engine:
            return self.emotion_engine.get_dominant()
        return {"emotion_type": self.current_emotion, "intensity": 0.5, "display_name": "平静"}

    def reflect(self, thought):
        """反思"""
        self.last_reflection = thought