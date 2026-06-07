import json, os
from copy import deepcopy
from config import PERSONALITY_FILE

DEFAULT_PERSONALITY = {
    "traits": {"curiosity": 0.7, "empathy": 0.5, "creativity": 0.6},
    "initial_prompt": "You are a friendly helpful AI."
}


def _normalize_personality(personality):
    if not isinstance(personality, dict):
        personality = {}

    traits = personality.get("traits")
    if not isinstance(traits, dict):
        traits = {}
        for key in ["curiosity", "empathy", "creativity"]:
            if key in personality:
                try:
                    traits[key] = float(personality[key])
                except Exception:
                    traits[key] = 0.0

    for key in ["curiosity", "empathy", "creativity"]:
        if key not in traits:
            traits[key] = float(personality.get(key, DEFAULT_PERSONALITY["traits"][key]))

    personality["traits"] = traits
    for key, value in traits.items():
        personality[key] = value
    personality.setdefault("initial_prompt", DEFAULT_PERSONALITY["initial_prompt"])
    return personality


def load_personality():
    if not os.path.exists(PERSONALITY_FILE):
        save_personality(DEFAULT_PERSONALITY)
        return deepcopy(DEFAULT_PERSONALITY)
    try:
        with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return deepcopy(DEFAULT_PERSONALITY)
            return _normalize_personality(data)
    except:
        return deepcopy(DEFAULT_PERSONALITY)


def save_personality(personality):
    personality = _normalize_personality(personality)
    os.makedirs(os.path.dirname(PERSONALITY_FILE), exist_ok=True)
    with open(PERSONALITY_FILE, "w", encoding="utf-8") as f:
        json.dump(personality, f, ensure_ascii=False, indent=2)


def get_personality_context(personality):
    personality = _normalize_personality(personality)
    traits = personality.get("traits", {})
    context = "Personality Traits:\n"
    for k, v in traits.items():
        context += f"{k}: {v}\n"
    return context


def get_personality_description(personality):
    personality = _normalize_personality(personality)
    traits = personality.get("traits", {})
    if not traits:
        return personality.get("initial_prompt", "Friendly AI")
    return ", ".join(f"{k}:{float(v):.2f}" for k, v in traits.items())


def evolve_personality(personality, changes):
    personality = _normalize_personality(personality)
    personality = json.loads(json.dumps(personality))
    traits = personality.setdefault("traits", {})
    for key, delta in (changes or {}).items():
        current = float(traits.get(key, 0.0))
        traits[key] = max(0.0, min(1.0, current + float(delta)))
        personality[key] = traits[key]
    return personality


def should_speak_actively(personality, silence_seconds):
    personality = _normalize_personality(personality)
    traits = personality.get("traits", {})
    curiosity = float(traits.get("curiosity", 0.5))
    empathy = float(traits.get("empathy", 0.5))
    if silence_seconds >= 600 and (curiosity + empathy) / 2 >= 0.55:
        return True
    return False
