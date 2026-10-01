# Humanaize2

A local AI desktop companion: web chat panel, local/cloud LLM, memory, skills (shell, web search, etc.), voice, and idle autonomous activities. MIT licensed.

> [中文](../README.md)

## Install

Download `Humanaize2-Setup-x86_64-vX.X.X.exe` from [Releases](https://github.com/A113NWu/Humanaize2-Project/releases) and run it. A portable `*-portable.zip` is also available.

Requirements: Windows 10/11 x64, 8GB+ RAM for local models. Bring your own GGUF model, or use a cloud OpenAI-compatible API.

## Startup

| How | Behavior |
|---|---|
| Double-click Humanaize2.exe (default) | Shows the "Humanaize2 log" window + tray icon; opens `http://127.0.0.1:8082` |
| `Humanaize2.exe --tray` | No log window; starts minimized to the system tray |
| Closing the log window | Hides the log; the app keeps running in the tray (it is not quitting) |
| Tray right-click | "Open dashboard" / "Quit Humanaize2" (use the tray menu to quit) |
| `humanaize2 boot -m cli` | Terminal CLI mode |

A Windows Firewall prompt may appear on first launch (because the server binds 0.0.0.0); click Allow.

## Configuration

Everything is configured in the **Settings** page of the web panel. Changes take effect immediately, no restart needed.

### 1. Model (configure this first)

Choose one:

- **Local model**: set `model_path` in Settings → Basic to the full path of a `.gguf` file (hot-swappable). The app launches the bundled llama-server on port 8080. On CPU-only machines, Qwen2.5-3B-Instruct Q4 or larger is recommended; heavily quantized sub-2B models tend to produce garbage.
- **Cloud model (OpenAI-compatible)**: check "Enable OpenAI API mode" and fill in:
  - API Key
  - Base URL (e.g. `https://api.qnaigc.com/v1`, any OpenAI-compatible gateway works)
  - Model name (e.g. `minimax/minimax-m3`)

`max_tokens` and `temperature` are on the same page.

### 2. Security (access from other devices)

Settings → Security:

- **Allow LAN access**: toggle. Off = localhost only. On = other devices on the same network can open `http://<PC-IP>:8082` (use a login password when enabling this).
- **Username/password**: once set, the dashboard requires login (7-day session). Leave the password field blank to keep the current one; clear the username to disable login.

### 3. Skills

There is a global skills toggle in Settings. Manage individual skills from the command line:

```
humanaize2 skills -list
humanaize2 skills -enable shell
humanaize2 skills -disable shell
humanaize2 skills -install skill.zip
```

The `shell` skill runs commands on your machine; enable it only in a trusted environment.

### 4. Prompt files (Prompt directory)

The **`Prompt\`** folder in the install directory contains ~40 `.txt` prompt files (`system_prompt.txt`, `agent_prompt.txt`, `should_answer_user.txt`, `social_decide.txt`, etc.):

- Edit them with any text editor. They are **read on every request — edits take effect immediately, no restart**.
- Upgrades never overwrite your edits; deleted files are restored to defaults on restart.

### 5. Data and memory

All state lives in the **`data\`** folder inside the install directory:

| File | Contents |
|---|---|
| `ui_settings.json` | All Settings-page options (model path, API key, toggles) |
| `memory.json` | Conversation memory (last 100 messages) |
| `personality.json` | Personality |
| `sensitive_words.txt` | Sensitive-word list (one per line, `#` comments, hot-reloaded) |
| `skills_config.json` | Skill enable/disable state |

To move to another PC, copy the whole `data\` folder.

### 6. Other customization

- **Wallpaper**: create an `Assets\` folder in the install directory and put `Background.jpg` (or `.jpeg`/`.png`) in it; refresh the page.
- **IoT / Guard / GAN / proactive talk**: toggles in the corresponding Settings sections (`iot_auto_start`, `guard_enabled`, `gan_enabled`, `auto_break_silence`).
- **Voice**: click the microphone button at the right of the chat input (red and pulsing = on). Speech is transcribed and sent automatically; replies are read aloud streamed. Typing without enabling the mic never triggers TTS. Transcription uses the browser Web Speech API (Chrome/Edge recommended); TTS uses Microsoft edge-tts (requires internet).

## Common commands

```
humanaize2 boot [-m cli|gui|win-gui]   # start (web panel by default)
humanaize2 settings                    # settings
humanaize2 skills -list|-enable|-disable|-install
humanaize2 check-server                # check the local llama-server
humanaize2 update [-f]                 # check for / force update
humanaize2 help
```

CLI chat commands: `/help` `/mem` `/status` `/gan` `/clear` `/quit`.

## Run from source

```
git clone https://github.com/A113NWu/Humanaize2-Project.git
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python src/core/windows_main.py
```

## Troubleshooting

- **Dashboard won't open**: check the log window for errors; make sure port 8082 is free; `http://127.0.0.1:8082/health` returning `ok` means the server is fine.
- **Empty / no replies**: verify the model path or the three cloud API fields. Some gateways require provisioning the inference service separately.
- **Connection errors with a system proxy on**: the app bypasses the system proxy. Turn off the proxy's "system proxy" switch when the local proxy isn't running.
- **Old behavior after upgrade**: hard-refresh the browser with Ctrl+F5.
