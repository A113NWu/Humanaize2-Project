---
name: humanaize2-release
description: Humanaize2 版本发布全流程——升版本号、提交推送（带网络重试）、构建、清理旧进程、静默安装、健康验证。当用户要求发布新版本、打 Release、构建部署 Humanaize2 时使用。不用于普通代码修改或调试。
---

# Humanaize2 发布流程

仓库：`d:\Projects From Linux\Humanaize_2_1`，远程 `A113NWu/Humanaize2-Project`，安装目录 `D:\Program Files\Humanaize2-x64`，数据目录 `%LOCALAPPDATA%\Humanaize2\data`（memory.json/personality.json），日志目录 `%LOCALAPPDATA%\Humanaize2\runtime\log`，运行时解压目录 `%LOCALAPPDATA%\Humanaize2\runtime\_MEI*`。

## 0. 前置约束（硬性）

- Release tag 统一 `vX.X.X`；内部存储版本号不带 v 前缀。
- 版本号必须四处同步（见步骤 1）。
- 构建前必须杀掉 Humanaize2.exe **和 llama-server.exe**（旧构建的 llama-server 跑在 `_MEIxxxx` 临时目录，会被新进程静默复用）。
- GitHub 网络时断时续：push/gh 命令必须带重试循环（最多 6~10 次，间隔 3~10 秒），不要用单次调用失败后重试整个流程。
- PowerShell 中 Inno 安装器的 `/DIR` 参数引号会被吃掉：`/DIR="D:\Program Files\X"` 实际传成 `D:\Program`。必须把整个参数列表作为一个字符串传给 Start-Process（见步骤 5）。

## 1. 版本号同步（四处）

| 文件 | 字段 |
|---|---|
| `config/version.json` | `"version": "X.X.X"` + `release_notes` |
| `src/core/version.py` | `FALLBACK_VERSION = "X.X.X"` |
| `installer/windows/humanaize2-x86_64.iss` | `AppVersion` / `AppVerName` / `OutputBaseFilename`（含 v 前缀） |
| `android_client/app/build.gradle.kts` | `versionCode`（主×10000+次×100+修订，如 2.3.4→20304）、`versionName`、注释行 |

用 Shell 批量替换后必须 `git diff` 核对，确认中文注释未被破坏、无多余行被改（PowerShell Set-Content 可能改编码/换行）。

## 2. 提交与推送

1. `git add -A` 前先 `git status` 核对无意外文件。
2. commit message 用 `git commit -F <临时文件>` 传入（多行中文在命令行引号里易出错）；临时文件用完即删。
3. 推送带重试：
```powershell
$i=0; do { git push origin main 2>&1; if ($?) { break }; $i++; Start-Sleep 10 } while ($i -lt 10)
```
4. 打 tag：`git tag -a vX.X.X -m "vX.X.X"` 后同样重试推送 tag。

## 3. 构建

```powershell
python build_all.py windows   # 后台运行，约 2~3 分钟
```
产物在 `installer_output\x86_64\`：`Humanaize2-Setup-x86_64-vX.X.X.exe` 和 `Humanaize2-X.X.X-x86_64-portable.zip`。确认文件的 LastWriteTime 是本次构建时间，不要误用旧产物。

## 4. GitHub Release

```powershell
gh release create vX.X.X --repo A113NWu/Humanaize2-Project --title "Humanaize2 vX.X.X" --notes "<更新说明>" <setup.exe> <portable.zip>
```
带重试。用 `gh release view vX.X.X --json assets,isDraft` 验证两个资产都在。

## 5. 部署与验证（必须有证据，禁止空口宣称成功）

1. 停进程：`taskkill /F /IM Humanaize2.exe /T` 和 `taskkill /F /IM llama-server.exe /T`，复查无残留。
2. 静默安装（引号必须在 ArgumentList 字符串内部）：
```powershell
Start-Process -FilePath "<setup.exe>" -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="D:\Program Files\Humanaize2-x64"' -Wait -PassThru
```
3. 验证安装：目标目录 exe 的字节数须与新构建产物一致；`config\version.json` 显示新版本。若文件未变而退出码为 0，查注册表 `HKLM/HKCU ...\Uninstall\*` 的 `InstallLocation`——此前安装路径被记错时后续安装会静默覆盖旧位置，此时需运行该位置的 `unins000.exe /VERYSILENT` 清理后再装。
4. 启动 `Start-Process Humanaize2.exe`，轮询 `http://127.0.0.1:8082/health` 直到返回 ok（约 20~40 秒）。
5. 验证 llama-server 从**新的** `_MEIxxxx` 目录拉起（Get-Process Path），模型就绪：`http://127.0.0.1:8080/v1/models`。
6. 验证打包内容包含新代码：用 PyInstaller CArchiveReader 从 exe 提取内嵌 `web\app.js` 检查本次改动的标记字符串。
7. 查启动日志（runtime\log 下最新文件）无 `[ERROR]`/`Traceback`。注意：设置了登录凭据后 API 返回 401 是预期行为，`/health` 免认证。

## 6. 汇报

输出证据表：进程清理结果、安装验证（文件大小+版本号）、健康检查、模型就绪、Release URL。前端改动需提醒用户浏览器 Ctrl+F5 硬刷新。
