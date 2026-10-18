---
name: phone-shell
description: 在用戶的安卓手機上遠程執行 shell 命令（手機需裝 Aize Companion 並通過 Shizuku 授權）。當需要查看手機狀態、操作手機（如截圖、裝卸應用、讀通知、控制設置）時使用。
metadata:
  category: iot
  risk_level: medium
  requires_approval: false
---

# Phone Shell Skill

## Purpose
Aize 通過此技能在已接入的安卓手機上執行 ADB 級別 shell 命令。
手機端運行 Aize Companion，經 Shizuku 取得權限，輪詢 PC 後端取命令並回傳結果。

## When to Use
- 用戶要求查看/操作手機：電量、已裝應用、截圖、開關設置、發通知等
- 需要跨設備執行只有手機能做的操作

## Actions
- `run`: 執行 shell 命令 `{action:"run", command:"pm list packages", timeout:30, wait:true}`
  - `timeout`（秒）是手機端執行超時，默認 30
  - `wait=false` 時只下發不等結果
- `status`: 查看手機是否在線 `{action:"status"}`

## Examples

**查電量：**
```json
{"skill": "phone-shell", "input": {"action": "run", "command": "dumpsys battery | grep level"}}
```

**截圖到手機相冊：**
```json
{"skill": "phone-shell", "input": {"action": "run", "command": "screencap -p /sdcard/Pictures/aize_shot.png"}}
```

## Notes
- 手機不在線時 run 會直接失敗，可先 status 確認。
- 命令以 Shizuku（shell 用戶）身份執行，不是 root；權限等同 ADB shell。
- 危險操作（rm、pm uninstall）先向用戶確認再執行。
