---
name: detect-emotion
description: Use the camera to detect the user's current emotional state. Call this when you want to understand how the user is feeling. Returns dominant emotion and confidence level.
metadata:
  category: utility
  risk_level: low
  requires_approval: false
  version: 1.0.0
  author: Humanaize Team
---

# Detect Emotion

## Purpose
Analyze the user's facial expression through the webcam to determine their current emotional state.

## When to Use

- When the user seems upset or frustrated
- When you want to personalize your response based on user mood
- When the user asks "how am I feeling?" or similar
- Before making important decisions that might be affected by user emotions
- When you notice unusual user behavior

## Input Format

```json
{"skill": "detect-emotion", "input": "detect"}
```

Or simply:

```json
{"skill": "detect-emotion", "input": ""}
```

## Output

Returns a dictionary with:
- `dominant`: The primary emotion detected (happy, sad, angry, surprised, fearful, disgust, neutral)
- `confidence`: Confidence score between 0 and 1
- `error`: Error message if detection failed

## Example

**Input:**
```json
{"skill": "detect-emotion", "input": ""}
```

**Output:**
```json
{"dominant": "happy", "confidence": 0.87}
```

## Notes

- Requires camera access permission
- Works best with good lighting
- Detection may be less accurate for multiple faces
- If camera is unavailable, returns "neutral" with 0 confidence