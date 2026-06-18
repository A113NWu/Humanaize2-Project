---
name: reminder
description: Set reminders and timers. Use this when you need to remind the user about something at a specific time or after a delay.
metadata:
  category: utility
  risk_level: low
  requires_approval: false
---

# Reminder Skill

## Purpose
Set reminders and timers for the user.

## When to Use
- Setting time-based reminders
- Creating countdown timers
- Scheduling notifications
- Managing time-sensitive tasks

## Input Format
Provide the reminder details as a JSON object:

```json
{
  "skill": "reminder",
  "input": {
    "message": "Remember to drink water",
    "delay_minutes": 30
  }
}
```

## Parameters
- `message` (required): The reminder message
- `delay_minutes` (required): Delay in minutes before the reminder
- `repeat` (optional): Whether to repeat (default: false)

## Output
Returns confirmation and scheduled time.

## Examples

**Set a reminder:**
```json
{"skill": "reminder", "input": {"message": "Meeting in 10 minutes", "delay_minutes": 10}}
```

**Set a repeating reminder:**
```json
{"skill": "reminder", "input": {"message": "Take a break", "delay_minutes": 60, "repeat": true}}
```