//! Aize 桌面控制状态读取——直接读数据文件，不依赖 HTTP API。
//!
//! 状态源（与 skills/computer-control 约定一致）：
//!   <data>/desktop_control_state.json   运行状态（active/goal/steps/action...）
//!   <data>/desktop_control.stop         急停信号（存在即视为已请求停止）
//!   ui_settings.json                    desktop_control_enabled
//! HTTP API 线程偶发整体卡死（连 /health 都无响应），文件态永远可用。

use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Default)]
pub struct Status {
    pub reachable: bool, // 是否找到了 Aize 数据目录
    pub enabled: bool,   // desktop_control_enabled
    pub stopped: bool,   // 是否存在急停文件
    pub active: bool,    // 是否正在执行 run_goal
    pub autopilot: bool, // 是否处于 Autopilot（主人授权后的自由接管）
    pub transient: bool, // 单步动作写入的瞬时状态（几秒无更新即视为结束）
    pub goal: String,
    pub steps: i64,
    pub max_steps: i64,
    pub observation: String,
    pub action: String,
}

struct Paths {
    state: PathBuf,
    stop: PathBuf,
    settings: PathBuf,
}

/// (数据目录, 设置文件) 候选，按优先级排列
fn candidates() -> Vec<(PathBuf, PathBuf)> {
    let mut v: Vec<(PathBuf, PathBuf)> = Vec::new();
    if let Ok(dir) = std::env::var("AIZE_DATA_DIR") {
        let d = PathBuf::from(dir);
        v.push((d.clone(), d.join("ui_settings.json")));
    }
    for base in [
        r"D:\Program Files\Humanaize2-x64\data",
        r"C:\Program Files\Humanaize2-x64\data",
    ] {
        let d = PathBuf::from(base);
        v.push((d.clone(), d.join("ui_settings.json")));
    }
    if let Ok(home) = std::env::var("USERPROFILE") {
        let d = PathBuf::from(home).join(".humanaize2").join("data");
        v.push((d.clone(), d.join("ui_settings.json")));
    }
    // 开发仓库（源码运行态）：状态在 data/，设置在 src/core/ui/data/
    let dev = PathBuf::from(r"D:\Projects From Linux\Humanaize_2_1");
    v.push((
        dev.join("data"),
        dev.join(r"src\core\ui\data\ui_settings.json"),
    ));
    v
}

fn resolve() -> Option<Paths> {
    for (data, settings) in candidates() {
        if data.is_dir() {
            return Some(Paths {
                state: data.join("desktop_control_state.json"),
                stop: data.join("desktop_control.stop"),
                settings,
            });
        }
    }
    None
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

pub fn fetch_status() -> Status {
    let mut st = Status::default();
    let Some(p) = resolve() else { return st };
    st.reachable = true;
    st.enabled = std::fs::read_to_string(&p.settings)
        .ok()
        .and_then(|s| json_bool(&s, "desktop_control_enabled"))
        .unwrap_or(true);
    st.stopped = p.stop.exists();
    if let Ok(body) = std::fs::read_to_string(&p.state) {
        st.active = json_bool(&body, "active").unwrap_or(false);
        st.autopilot = json_bool(&body, "autopilot").unwrap_or(false);
        st.transient = json_bool(&body, "transient").unwrap_or(false);
        st.goal = json_str(&body, "goal").unwrap_or_default();
        st.steps = json_i64(&body, "steps").unwrap_or(0);
        st.max_steps = json_i64(&body, "max_steps").unwrap_or(0);
        st.observation = json_str(&body, "observation").unwrap_or_default();
        st.action = json_str(&body, "action").unwrap_or_default();
        // active 但长时间未刷新 → 写状态的进程已死/动作已结束，视为未运行
        // 瞬时状态（单步动作）6 秒过期，Autopilot 600 秒，run_goal 120 秒过期
        let updated = json_i64(&body, "updated_at").unwrap_or(0);
        let ttl = if st.transient {
            6
        } else if st.autopilot {
            600
        } else {
            120
        };
        if st.active && (updated <= 0 || now_secs() - updated > ttl) {
            st.active = false;
        }
    }
    st
}

/// 紧急停止 = 写急停文件（跨进程生效，与 computer-control 的 _request_stop 等价）
pub fn post_stop() -> bool {
    let Some(p) = resolve() else { return false };
    std::fs::write(&p.stop, now_secs().to_string()).is_ok()
}

/// 解除急停 = 删除急停文件，恢复控制
pub fn clear_stop() -> bool {
    let Some(p) = resolve() else { return false };
    match std::fs::remove_file(&p.stop) {
        Ok(()) => true,
        Err(e) => e.kind() == std::io::ErrorKind::NotFound,
    }
}

// ------------------------------------------------------------ 极简 JSON 解析

fn find_value<'a>(s: &'a str, key: &str) -> Option<&'a str> {
    let pat = format!("\"{}\"", key);
    let start = s.find(&pat)? + pat.len();
    let rest = s[start..].trim_start();
    let rest = rest.strip_prefix(':')?.trim_start();
    Some(rest)
}

fn json_bool(s: &str, key: &str) -> Option<bool> {
    let v = find_value(s, key)?;
    if v.starts_with("true") {
        Some(true)
    } else if v.starts_with("false") {
        Some(false)
    } else {
        None
    }
}

fn json_i64(s: &str, key: &str) -> Option<i64> {
    let v = find_value(s, key)?;
    let end = v
        .find(|c: char| !(c.is_ascii_digit() || c == '-' || c == '+'))
        .unwrap_or(v.len());
    v[..end].parse().ok()
}

fn json_str(s: &str, key: &str) -> Option<String> {
    let v = find_value(s, key)?;
    if !v.starts_with('"') {
        return None;
    }
    Some(json_str_bytes(v))
}

/// 字节级字符串提取（UTF-8 安全）：找到未转义的结束引号，返回反转义后文本。
fn json_str_bytes(v: &str) -> String {
    let bytes = v.as_bytes();
    let mut raw: Vec<u8> = Vec::with_capacity(bytes.len());
    let mut i = 1;
    while i < bytes.len() {
        let b = bytes[i];
        if b == b'"' {
            break;
        }
        if b == b'\\' && i + 1 < bytes.len() {
            match bytes[i + 1] {
                b'n' => raw.push(b'\n'),
                b't' => raw.push(b'\t'),
                b'r' => raw.push(b'\r'),
                other => {
                    if other == b'u' && i + 5 < bytes.len() {
                        if let Ok(cp) = u32::from_str_radix(&v[i + 2..i + 6], 16) {
                            let mut tmp = [0u8; 4];
                            if let Some(c) = char::from_u32(cp) {
                                raw.extend_from_slice(c.encode_utf8(&mut tmp).as_bytes());
                            }
                        }
                        i += 4;
                    } else {
                        raw.push(other);
                    }
                }
            }
            i += 2;
            continue;
        }
        raw.push(b);
        i += 1;
    }
    String::from_utf8_lossy(&raw).into_owned()
}
