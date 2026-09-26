# Dashboard 安全性增強：局域網訪問開關 + 賬戶密碼登錄

## Context

用戶此前要求 Dashboard 設置頁具備三項能力：Skills 開關、局域網訪問控制、賬戶密碼登錄。
調研結論：**Skills 開關已完整存在**（設置 → 技能管理，勾選即調 `/api/skills/toggle` 持久化到 skills_config.json）。
本次只需新增後兩項，全部在「安全性」板塊落地。

現狀：
- HTTP 服務在 [windows_main.py:208](file:///d:/Projects From Linux/Humanaize_2_1/src/core/windows_main.py#L208) 綁定 `127.0.0.1:8082`（局域網本來就訪問不到）
- 設置持久化：`_settings_defaults()` / `_read_settings_raw()` / `_handle_save_settings()`（[thinking_engine_api.py:701-770](file:///d:/Projects From Linux/Humanaize_2_1/src/core/thinking_engine_api.py#L701-L770)），保存時以 defaults 的 key 為白名單合併
- 無任何認證機制

## 實施方案

### 1. 後端 `src/core/thinking_engine_api.py`

**新增設置默認值**（`_settings_defaults`）：
- `allow_lan_access: False`、`web_auth_username: ""`、`web_auth_password_hash: ""`

**設置視圖脫敏**（`_load_settings`）：不返回 hash，改返回 `web_auth_enabled: bool` + `web_auth_username`。

**保存邏輯**（`_handle_save_settings`）：
- `web_auth_password` 不是 defaults key，會被白名單過濾掉——在過濾前單獨取出處理：
  - 非空 → `salt$sha256(salt+password)` 寫入 `web_auth_password_hash`（隨機 salt，`secrets.token_hex(8)`）
  - 空串 → 不修改（與 token 的「留空不修改」語義一致）
- `web_auth_username` 被清空時，同時清空 hash（=關閉登錄）

**局域網門禁**（do_GET/do_POST 最前面）：
- `client_address[0]` 不是 `127.0.0.1`/`::1` 且 `allow_lan_access=False` → 403「局域网访问未启用」
- 熱生效，無需重啟

**會話認證**：
- 進程內存 `_SESSIONS = {token: expiry}`（7 天），重啟需重新登錄
- 新端點：`POST /api/login`（校驗賬密→發 token，`Set-Cookie: humanaize_session=<token>; HttpOnly; SameSite=Strict`）、`POST /api/logout`
- 豁免路徑：`/api/login`、`/health`（狀態燈用）；其餘全部需要認證
- 認證方式：Cookie 或 `Authorization: Bearer <token>`（QQ-bot 等 API 客戶端可先 login 拿 token）
- 未認證訪問 `/` → 返回內聯登錄頁 HTML（橙色主題、簡潔表單，JS POST /api/login 成功後刷新）
- 未認證訪問 API → 401 JSON

### 2. 綁定地址改為 `0.0.0.0`

- [windows_main.py:208](file:///d:/Projects From Linux/Humanaize_2_1/src/core/windows_main.py#L208) 與 [main.py:1098](file:///d:/Projects From Linux/Humanaize_2_1/src/core/main.py#L1098)：`start_api_server(host='0.0.0.0', ...)`
- 安全性由請求級門禁保證（默認拒絕局域網）；這樣開關才能熱生效
- 注意：首次可能觸發 Windows 防火牆提示，需允許

### 3. 前端

**[index.html](file:///d:/Projects From Linux/Humanaize_2_1/src/core/web/index.html) 安全性板塊新增**：
```
網絡訪問：☐ 允許局域網設備訪問此面板（說明：開啟後同局域網設備可通過 http://<本機IP>:8082 訪問）
賬戶登錄：賬戶名 [input] 密碼 [password，留空不修改]（說明：設置後打開面板需先登錄；清空賬戶名保存即關閉登錄）
```

**[app.js](file:///d:/Projects From Linux/Humanaize_2_1/src/core/web/app.js)**：
- `loadSettings()`：`web_auth_enabled=true` 時密碼框 placeholder 顯示「已設置密碼（留空不修改）」
- 所有 `/api/*` fetch 加 401 處理：`location.reload()`（服務器會在 `/` 返回登錄頁）
- EventSource `/api/events` 走同源 Cookie，登錄後自動可用

### 4. 部署

後端有改動 → 提交後重建 exe 部署（web/ 目錄順帶複製到 exe 旁，驗證上一輪修的靜態文件熱更新）。

## 驗證

1. 語法檢查 + 單獨測試認證 helper（hash/verify、session 過期）
2. 重建部署後 curl 驗證：
   - 未設密碼：`GET /` 正常 200
   - 設置賬密後：`GET /api/settings` → 401；`POST /api/login` 錯密碼 → 401，對密碼 → 200 + Cookie；帶 Cookie 訪問 → 200
   - 模擬局域網 IP（或從手機訪問）：`allow_lan_access=false` → 403；開啟後 → 登錄頁/正常
3. 瀏覽器手動過一遍：設置密碼 → 刷新出登錄頁 → 登錄 → 設置頁可見新板塊
