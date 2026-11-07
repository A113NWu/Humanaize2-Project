//! aize-status —— WinIsland 插件（ABI v2）：
//! 灵动岛上显示 Aize 桌面控制状态；托盘菜单 / 全局热键 Ctrl+Alt+Shift+S 紧急停止。

mod abi;
pub mod client;

use abi::*;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::ptr;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

struct PluginState {
    token: PluginToken,
    context_api: ContextApiV2,
    command_api: Option<CommandApiV2>,
    cmd_id: ResourceId,
    shutdown: AtomicBool,
    worker: Mutex<Option<JoinHandle<()>>>,
}

unsafe impl Send for PluginState {}
unsafe impl Sync for PluginState {}

// ---------------------------------------------------------------- 工具

fn truncate_chars(s: &str, max_bytes: usize) -> String {
    if s.len() <= max_bytes {
        return s.to_string();
    }
    let mut end = max_bytes;
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    s[..end].to_string()
}

fn render(st: &client::Status) -> (u32, String, String, String) {
    if !st.reachable {
        return (
            PRIORITY_LOW,
            "Aize 离线".into(),
            "无法连接 Aize API（127.0.0.1），服务未运行。".into(),
            "Aize 离线".into(),
        );
    }
    if st.http_code != 200 {
        return (
            PRIORITY_LOW,
            "Aize 状态未知".into(),
            format!("API 返回 HTTP {}（Aize 版本过旧，请升级到 v2.4.8+）。", st.http_code),
            "Aize 状态未知".into(),
        );
    }
    if !st.enabled {
        return (
            PRIORITY_LOW,
            "桌面控制已禁用".into(),
            "Aize 当前未启用桌面控制（desktop_control_enabled = false）。".into(),
            "控制已禁用".into(),
        );
    }
    if st.active {
        let goal = if st.goal.is_empty() { "（无描述）" } else { st.goal.as_str() };
        let mut body = format!("目标：{}\n进度：{}/{}", goal, st.steps, st.max_steps);
        if !st.observation.is_empty() {
            body.push_str(&format!("\n最近观察：{}", st.observation));
        }
        body.push_str("\n急停：托盘菜单 WinIsland → 命令，或按 Ctrl+Alt+Shift+S");
        return (
            PRIORITY_HIGH,
            "⚠ Aize 正在控制电脑".into(),
            body,
            format!("Aize 控制中 {}/{}", st.steps, st.max_steps),
        );
    }
    if st.stopped {
        return (
            PRIORITY_MEDIUM,
            "Aize 已紧急停止".into(),
            "检测到急停信号，桌面控制已中止。".into(),
            "Aize 已停止".into(),
        );
    }
    (
        PRIORITY_LOW,
        "Aize 待机".into(),
        "桌面控制就绪，当前无任务。".into(),
        "Aize 待机".into(),
    )
}

fn api_port() -> u16 {
    std::env::var("AIZE_API_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(8082)
}

// ---------------------------------------------------------------- 轮询线程

fn worker_loop(state: &'static PluginState) {
    let create = state.context_api.create;
    let update = state.context_api.update;
    let mut ctx_id: ResourceId = 0;

    while !state.shutdown.load(Ordering::SeqCst) {
        let st = client::fetch_status(api_port());
        let (priority, title, body, compact) = render(&st);
        let fp = format!("{}|{}|{}|{}", priority, title, body, compact);

        if fp != state.fingerprint_locked() {
            let data = ContextDataV2::new(
                priority,
                &truncate_chars(&title, 255),
                &truncate_chars(&body, 511),
                &truncate_chars(&compact, 127),
            );
            unsafe {
                let ctx = state.context_api.prefix.context;
                if ctx_id == 0 {
                    if let Some(create) = create {
                        let mut out: ResourceId = 0;
                        if create(ctx, state.token, &data, &mut out) == STATUS_OK {
                            ctx_id = out;
                        }
                    }
                } else if let Some(update) = update {
                    update(ctx, state.token, ctx_id, &data);
                }
            }
            state.set_fingerprint(fp);
        }

        let deadline = Instant::now() + Duration::from_secs(2);
        while Instant::now() < deadline {
            if state.shutdown.load(Ordering::SeqCst) {
                break;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
    }

    // 释放 context
    if ctx_id != 0 {
        if let Some(release) = state.context_api.release {
            unsafe {
                release(state.context_api.prefix.context, state.token, ctx_id);
            }
        }
    }
}

impl PluginState {
    fn fingerprint_locked(&self) -> String {
        FP.lock().unwrap().clone()
    }
    fn set_fingerprint(&self, fp: String) {
        *FP.lock().unwrap() = fp;
    }
}

static FP: Mutex<String> = Mutex::new(String::new());

// ---------------------------------------------------------------- 急停命令回调

unsafe extern "C" fn on_stop_command(_data: *mut c_void, _event: *const PluginEventV2) {
    let _ = catch_unwind(AssertUnwindSafe(|| {
        std::thread::spawn(|| {
            client::post_stop(api_port());
            // 清指纹，下一轮轮询立即刷新
            *FP.lock().unwrap() = String::new();
        });
    }));
}

// ---------------------------------------------------------------- 插件入口回调

unsafe extern "C" fn create(info: *const PluginCreateInfoV2, out_handle: *mut *mut c_void) -> i32 {
    let r = catch_unwind(AssertUnwindSafe(|| -> i32 {
        if info.is_null() || out_handle.is_null() {
            return 1;
        }
        let info = &*info;
        if info.host_api.is_null() {
            return 1;
        }
        let host = &*info.host_api;
        let query = match host.query {
            Some(q) => q,
            None => return 1,
        };
        // 查询 Context / Command 服务表
        let ctx_ptr = query(host.prefix.context, IFACE_CONTEXT, IFACE_VERSION_1);
        if ctx_ptr.is_null() {
            return 1;
        }
        let context_api = std::ptr::read_unaligned(ctx_ptr as *const ContextApiV2);
        let cmd_ptr = query(host.prefix.context, IFACE_COMMAND, IFACE_VERSION_1);
        let command_api = if cmd_ptr.is_null() {
            None
        } else {
            Some(std::ptr::read_unaligned(cmd_ptr as *const CommandApiV2))
        };

        let mut state = Box::new(PluginState {
            token: info.plugin_token,
            context_api,
            command_api,
            cmd_id: 0,
            shutdown: AtomicBool::new(false),
            worker: Mutex::new(None),
        });

        // 注册急停命令（托盘菜单 + Ctrl+Alt+Shift+S）
        if let Some(cmd_api) = state.command_api {
            if let Some(register) = cmd_api.register {
                let spec = CommandSpecV2 {
                    struct_size: std::mem::size_of::<CommandSpecV2>() as u32,
                    flags: COMMAND_ENABLED | COMMAND_TRAY,
                    key: str_to_fixed::<64>("emergency-stop"),
                    title: str_to_fixed::<256>("⛔ 紧急停止 Aize 桌面控制"),
                    hotkey_modifiers: MOD_CONTROL | MOD_ALT | MOD_SHIFT,
                    hotkey_key: 0x53, // 'S'
                    callback: Some(on_stop_command),
                    callback_data: ptr::null_mut(),
                };
                let mut id: ResourceId = 0;
                if register(cmd_api.prefix.context, state.token, &spec, &mut id) == STATUS_OK {
                    state.cmd_id = id;
                }
            }
        }

        // 'static 引用供轮询线程使用；destroy 时回收
        let state_ptr = Box::into_raw(state);
        let state_ref: &'static PluginState = &*state_ptr;
        let handle = std::thread::spawn(move || worker_loop(state_ref));
        *(*state_ptr).worker.lock().unwrap() = Some(handle);

        *out_handle = state_ptr as *mut c_void;
        STATUS_OK
    }));
    match r {
        Ok(code) => code,
        Err(_) => 7,
    }
}

unsafe extern "C" fn shutdown(handle: *mut c_void) -> i32 {
    let r = catch_unwind(AssertUnwindSafe(|| {
        if handle.is_null() {
            return STATUS_OK;
        }
        let state = &*(handle as *const PluginState);
        state.shutdown.store(true, Ordering::SeqCst);
        let worker = state.worker.lock().unwrap().take();
        if let Some(t) = worker {
            let _ = t.join();
        }
        // 释放急停命令
        if state.cmd_id != 0 {
            if let Some(cmd_api) = state.command_api {
                if let Some(release) = cmd_api.release {
                    release(cmd_api.prefix.context, state.token, state.cmd_id);
                }
            }
        }
        STATUS_OK
    }));
    match r {
        Ok(code) => code,
        Err(_) => 7,
    }
}

unsafe extern "C" fn destroy(handle: *mut c_void) {
    let _ = catch_unwind(AssertUnwindSafe(|| {
        if !handle.is_null() {
            drop(Box::from_raw(handle as *mut PluginState));
        }
    }));
}

// ---------------------------------------------------------------- 描述符导出

static DESCRIPTOR: PluginDescriptorV2 = PluginDescriptorV2 {
    struct_size: std::mem::size_of::<PluginDescriptorV2>() as u32,
    abi_version: ABI_VERSION_2,
    capabilities: CAP_CONTEXT | CAP_COMMAND,
    metadata: PluginMetadataC {
        id: str_to_fixed::<64>("aize-status"),
        name: str_to_fixed::<128>("Aize Status"),
        version: str_to_fixed::<32>("0.1.0"),
        author: str_to_fixed::<128>("Humanaize"),
        description: str_to_fixed::<256>("显示 Aize 桌面控制状态；托盘命令或 Ctrl+Alt+Shift+S 紧急停止"),
    },
    create: Some(create),
    shutdown: Some(shutdown),
    destroy: Some(destroy),
    on_tick: None,
};

#[no_mangle]
pub unsafe extern "C" fn winisland_plugin_entry_v2() -> *const PluginDescriptorV2 {
    &DESCRIPTOR
}
