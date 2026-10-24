---
name: mcp-client
description: MCP 客戶端：接入並調用外部 MCP 服務器（如 Tulpa 的 QQ/微信查詢、群聊）。input 例：{"command":"call","server":"tulpa","tool":"get_data_status","arguments":{}}；先用 list_servers 看已配置服務器，再用 list_tools 列出工具
metadata:
  category: integration
  risk_level: medium
  requires_approval: false
  version: 1.0.0
  config_ui: config_ui.html
  config_file: config.json
  config_secret_fields:
    - servers.*.token
---

# MCP 客戶端技能

以 HTTP Streamable 傳輸（JSON-RPC 2.0）接入外部 MCP 服務器，讓 Aize 直接使用外部工具。
典型場景：接 Tulpa 查 QQ / 微信聊天記錄、讀取群文件、按授權參與群聊。

## 動作

| command | 作用 | 必要參數 |
| --- | --- | --- |
| `list_servers` | 列出已配置的服務器 | — |
| `list_tools` | 列出服務器提供的工具與參數 | `server`（只有一個時可省） |
| `call` | 調用指定工具 | `server`、`tool`、`arguments` |
| `ping` | 測試連線與協議握手 | `server`（可省） |
| `refresh` | 清除連線快取（改配置後） | — |

## 調用示例

```json
{"skill": "mcp-client", "input": {"command": "list_tools", "server": "tulpa"}}
```

```json
{"skill": "mcp-client", "input": {"command": "call", "server": "tulpa", "tool": "get_data_status", "arguments": {}}}
```

## 行為說明

- 首次調用某服務器時自動完成 `initialize` 握手，會話 id 在進程內快取。
- 影像類返回會存到系統臨時目錄 `humanaize-mcp/`，結果裡給出文件路徑，可再用 `vision` 技能識圖。
- 長文本按 `max_result_chars` 截斷（預設 20000），可在配置裡調整。
- 工具調用是持續授權：MCP 服務器側已授權的寫操作會直接執行，調用前先確認目標與範圍。

## 配置

Dashboard → 技能 → MCP 客戶端 → 配置，可新增/刪除服務器：

- `url`：MCP 端點，Tulpa 形如 `http://127.0.0.1:18777/mcp`（保留 `/mcp`）
- `token`：Bearer Token，Tulpa 在「外部 Agent / MCP」頁創建連接後取得
- `timeout`：單次工具調用超時秒數，Tulpa 建議 240
- `enabled`：停用後不會出現在可用服務器列表

配置寫在 `config.json`，token 在網頁讀取時脫敏為 `configured`。
