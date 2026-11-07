//! Aize 本地 HTTP API 客户端（手写极简 HTTP/1.0 + JSON 提取，零依赖）。

use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::Duration;

#[derive(Debug, Clone, Default)]
pub struct Status {
    pub reachable: bool,   // TCP 是否连上并收到响应
    pub http_code: u16,    // HTTP 状态码（0 = 无响应）
    pub enabled: bool,     // desktop_control_enabled
    pub stopped: bool,     // 是否存在急停文件
    pub active: bool,      // 是否正在执行 run_goal
    pub goal: String,
    pub steps: i64,
    pub max_steps: i64,
    pub observation: String,
}

fn http_exchange(port: u16, request: &str) -> Option<(u16, String)> {
    let addr = format!("127.0.0.1:{}", port);
    let mut stream = TcpStream::connect_timeout(
        &addr.parse().ok()?,
        Duration::from_millis(800),
    )
    .ok()?;
    stream
        .set_read_timeout(Some(Duration::from_millis(1500)))
        .ok();
    stream
        .set_write_timeout(Some(Duration::from_millis(800)))
        .ok();
    stream.write_all(request.as_bytes()).ok()?;
    stream.shutdown(std::net::Shutdown::Write).ok();

    // read_to_end 在超时中断时直接失败；改为循环读保留已收到的数据
    let mut buf = Vec::with_capacity(4096);
    let mut chunk = [0u8; 2048];
    loop {
        match stream.read(&mut chunk) {
            Ok(0) => break,
            Ok(n) => buf.extend_from_slice(&chunk[..n]),
            Err(_) => break,
        }
        if buf.len() > 256 * 1024 {
            break;
        }
    }
    let raw = String::from_utf8_lossy(&buf).into_owned();
    let mut parts = raw.splitn(2, "\r\n\r\n");
    let head = parts.next().unwrap_or("");
    let body = parts.next().unwrap_or("").to_string();
    let code = head
        .split_whitespace()
        .nth(1)
        .and_then(|s| s.parse::<u16>().ok())
        .unwrap_or(0);
    Some((code, body))
}

pub fn fetch_status(port: u16) -> Status {
    let req = format!(
        "GET /api/desktop-control/status HTTP/1.0\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
        port
    );
    let mut st = Status::default();
    let Some((code, body)) = http_exchange(port, &req) else {
        return st;
    };
    st.reachable = true;
    st.http_code = code;
    if code != 200 {
        return st;
    }
    st.enabled = json_bool(&body, "enabled").unwrap_or(false);
    st.stopped = json_bool(&body, "stopped").unwrap_or(false);

    // running 是嵌套对象：先定位 "running"{ ... } 再在范围内取字段
    if let Some(running) = json_object(&body, "running") {
        st.active = json_bool(running, "active").unwrap_or(false);
        st.goal = json_str(running, "goal").unwrap_or_default();
        st.steps = json_i64(running, "steps").unwrap_or(0);
        st.max_steps = json_i64(running, "max_steps").unwrap_or(0);
        st.observation = json_str(running, "observation").unwrap_or_default();
    }
    st
}

pub fn post_stop(port: u16) -> bool {
    let req = format!(
        "POST /api/desktop-control/stop HTTP/1.0\r\nHost: 127.0.0.1:{}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
        port
    );
    match http_exchange(port, &req) {
        Some((code, _)) => (200..300).contains(&code),
        None => false,
    }
}

// ------------------------------------------------------------ 极简 JSON 解析

/// 提取 key 对应的子对象原文（返回 &str 切片）
fn json_object<'a>(s: &'a str, key: &str) -> Option<&'a str> {
    let pat = format!("\"{}\"", key);
    let start = s.find(&pat)? + pat.len();
    let rest = s[start..].trim_start();
    let rest = rest.strip_prefix(':')?.trim_start();
    if !rest.starts_with('{') {
        return None;
    }
    // 找到配对的右括号
    let bytes = rest.as_bytes();
    let mut depth = 0i32;
    let mut in_str = false;
    let mut esc = false;
    for (i, &b) in bytes.iter().enumerate() {
        if in_str {
            if esc {
                esc = false;
            } else if b == b'\\' {
                esc = true;
            } else if b == b'"' {
                in_str = false;
            }
            continue;
        }
        match b {
            b'"' => in_str = true,
            b'{' => depth += 1,
            b'}' => {
                depth -= 1;
                if depth == 0 {
                    return Some(&rest[..=i]);
                }
            }
            _ => {}
        }
    }
    None
}

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
