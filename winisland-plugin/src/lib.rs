//! aize-status —— WinIsland 插件（ABI v2）。
//!
//! 收起态是一枚对称的小胶囊：左边状态球、中间时间 + 状态、右边急停钮。
//! 插件不再占用整条岛，宿主原本的时钟与自动收起行为都保留。
//! 键盘兜底热键：Ctrl+Alt+Shift+S（不进托盘菜单）。

mod abi;
pub mod client;
mod draw;
mod icon;

use abi::*;
use draw::{Color, List, Rect, ALIGN_CENTER, ALIGN_LEFT};
use std::ffi::c_void;
use std::ptr;
use std::sync::atomic::{AtomicBool, AtomicPtr, Ordering};
use std::sync::Mutex;
use std::thread::JoinHandle;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const COMPACT_W: f32 = 620.0;
const COMPACT_H: f32 = 36.0;
const SURFACE_KEY: &str = "aize-status-compact";
const FONT_UI: &str = "Microsoft YaHei UI";
const FONT_NUM: &str = "Segoe UI";
const BTN_ID: u64 = 1;

struct State {
    token: PluginToken,
    surface_api: SurfaceApiV2,
    activity_api: Option<ActivityApiV2>,
    input_api: Option<InputApiV2>,
    events_api: Option<EventsApiV2>,
    system_api: Option<SystemApiV2>,
    command_api: Option<CommandApiV2>,
    compact: WidgetId,
    activity: ResourceId,
    event_sub: ResourceId,
    cmd: ResourceId,
    shutdown: AtomicBool,
    /// 岛内急停按钮被点击（或热键触发）
    stop_press: AtomicBool,
    worker: Mutex<Option<JoinHandle<()>>>,
}

static STATE: AtomicPtr<State> = AtomicPtr::new(ptr::null_mut());

unsafe impl Send for State {}
unsafe impl Sync for State {}

// ---------------------------------------------------------------- 状态 → 配色

#[derive(Clone, Copy, PartialEq)]
enum Kind {
    Offline,
    Disabled,
    Active,
    Autopilot,
    Stopped,
    Idle,
}

struct Palette {
    accent: Color,
    on: Color,
    sub: Color,
    orb_top: (u8, u8, u8),
    orb_bot: (u8, u8, u8),
}

fn kind_of(st: &client::Status) -> Kind {
    if !st.reachable {
        Kind::Offline
    } else if !st.enabled {
        Kind::Disabled
    } else if st.active {
        if st.autopilot {
            Kind::Autopilot
        } else {
            Kind::Active
        }
    } else if st.stopped {
        Kind::Stopped
    } else {
        Kind::Idle
    }
}

fn palette(kind: Kind) -> Palette {
    match kind {
        Kind::Idle => Palette {
            accent: Color::rgb(0x46, 0xE3, 0xC3),
            on: Color::rgb(0xF2, 0xFB, 0xF9),
            sub: Color::rgb(0x9A, 0xB5, 0xB1),
            orb_top: (0x9C, 0xFF, 0xE8),
            orb_bot: (0x0B, 0x7C, 0x71),
        },
        Kind::Active => Palette {
            accent: Color::rgb(0xFF, 0x6B, 0x4F),
            on: Color::rgb(0xFF, 0xF5, 0xF2),
            sub: Color::rgb(0xCE, 0xAB, 0xA4),
            orb_top: (0xFF, 0xBE, 0x94),
            orb_bot: (0xB3, 0x2A, 0x1C),
        },
        Kind::Autopilot => Palette {
            accent: Color::rgb(0xA7, 0x8B, 0xFA),
            on: Color::rgb(0xF6, 0xF3, 0xFF),
            sub: Color::rgb(0xB6, 0xAC, 0xD8),
            orb_top: (0xD6, 0xC6, 0xFF),
            orb_bot: (0x49, 0x2B, 0xA8),
        },
        Kind::Stopped => Palette {
            accent: Color::rgb(0xFF, 0x77, 0xA8),
            on: Color::rgb(0xFF, 0xF2, 0xF7),
            sub: Color::rgb(0xD3, 0xAE, 0xBC),
            orb_top: (0xFF, 0xB6, 0xCB),
            orb_bot: (0x93, 0x1C, 0x41),
        },
        Kind::Offline => Palette {
            accent: Color::rgb(0x8C, 0xA4, 0xB8),
            on: Color::rgb(0xEC, 0xF1, 0xF6),
            sub: Color::rgb(0x9A, 0xA5, 0xB1),
            orb_top: (0xC6, 0xD4, 0xE0),
            orb_bot: (0x41, 0x54, 0x66),
        },
        Kind::Disabled => Palette {
            accent: Color::rgb(0xAF, 0x95, 0xFF),
            on: Color::rgb(0xF7, 0xF4, 0xFF),
            sub: Color::rgb(0xB9, 0xAE, 0xD3),
            orb_top: (0xD8, 0xC6, 0xFF),
            orb_bot: (0x55, 0x33, 0xA8),
        },
    }
}

fn lines_for(kind: Kind, st: &client::Status) -> (String, String) {
    match kind {
        Kind::Idle => (
            "Aize 待机".into(),
            "下一个目标 · 等待你的指令".into(),
        ),
        Kind::Active => {
            let action = if st.action.is_empty() {
                if st.observation.is_empty() {
                    "观察屏幕".to_string()
                } else {
                    clip_text(&st.observation, 80)
                }
            } else {
                clip_text(&st.action, 80)
            };
            if st.goal.is_empty() {
                // 单步动作（无明确目标）：正在逐动作控制电脑
                return ("Aize 正在操作电脑".into(), format!("现在执行 · {action}"));
            }
            let goal = clip_text(&st.goal, 160);
            (
                format!("下一个目标 · {goal}"),
                format!(
                    "现在执行 · {action} · {}/{} 步",
                    st.steps,
                    st.max_steps.max(st.steps)
                ),
            )
        }
        Kind::Autopilot => {
            let action = if st.action.is_empty() {
                "自己决定下一步".to_string()
            } else {
                clip_text(&st.action, 80)
            };
            let goal = if st.goal.is_empty() {
                "自己玩电脑".to_string()
            } else {
                clip_text(&st.goal, 140)
            };
            (
                format!("Autopilot · {goal}"),
                format!("现在执行 · {action} · 第 {} 步", st.steps.max(1)),
            )
        }
        Kind::Stopped => (
            "Aize 已紧急停止".into(),
            "桌面控制已中止 · 点左侧绿色按钮恢复".into(),
        ),
        Kind::Offline => (
            "Aize 离线".into(),
            "找不到本地数据目录 · Aize 未安装或未运行".into(),
        ),
        Kind::Disabled => (
            "桌面控制已禁用".into(),
            "设置中 desktop_control_enabled = false".into(),
        ),
    }
}

fn clip_text(s: &str, max_bytes: usize) -> String {
    if s.len() <= max_bytes {
        return s.to_string();
    }
    let mut end = max_bytes;
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    let mut out = s[..end].to_string();
    out.push('…');
    out
}

/// 粗略文字宽度估算（CJK 按 1em、ASCII 按 0.56em），用于右对齐。
fn est_width(s: &str, size: f32) -> f32 {
    s.chars()
        .map(|c| if c.is_ascii() { size * 0.56 } else { size })
        .sum()
}

// ---------------------------------------------------------------- 布局

fn compact_button(_w: f32, h: f32) -> Rect {
    Rect::new(12.0, (h - 24.0) * 0.5, 24.0, 24.0)
}

// ---------------------------------------------------------------- 收起态胶囊

fn render_compact(st: &client::Status, w: f32, h: f32, hm: &str, phase: f32) -> List {
    let kind = kind_of(st);
    let p = palette(kind);
    let (headline, detail) = lines_for(kind, st);

    let mut l = List::new(w, h);
    let radius = (h * 0.5).min(18.0);
    l.clip_round(Rect::new(0.0, 0.0, w, h), radius);
    // 纯黑底
    l.fill_rect(Rect::new(0.0, 0.0, w, h), Color::rgb(0, 0, 0));
    l.stroke_line(
        (radius, 1.0),
        (w - radius, 1.0),
        1.0,
        Color::rgba(255, 255, 255, 0x10),
    );

    // 左：急停按钮（红圈白方块）
    let btn = compact_button(w, h);
    let cx = btn.x + btn.w * 0.5;
    let cy = btn.y + btn.h * 0.5;
    let r = btn.w * 0.5;
    let resume = kind == Kind::Stopped;
    if kind == Kind::Active || kind == Kind::Autopilot {
        let pulse = (phase * std::f32::consts::TAU).sin() * 0.5 + 0.5;
        l.fill_circle(cx, cy, r + 2.0 + pulse * 2.0, p.accent.alpha(0x2A));
    }
    let (c_dark, c_main) = if resume {
        (Color::rgb(0x1B, 0x7A, 0x3E), Color::rgb(0x3E, 0xC9, 0x6E))
    } else {
        (Color::rgb(0xB3, 0x23, 0x2B), Color::rgb(0xEE, 0x44, 0x49))
    };
    l.fill_circle(cx, cy + 1.5, r, Color::rgba(0, 0, 0, 0x88));
    l.fill_circle(cx, cy, r, c_dark);
    l.fill_circle(cx, cy - 0.5, r - 1.0, c_main);
    l.fill_circle(cx, cy - r * 0.32, r * 0.52, Color::rgba(255, 255, 255, 0x22));
    if resume {
        // 白色播放三角（逐列竖条近似，表示「点击恢复」）
        for i in 0..9 {
            let hh = 4.5 * (1.0 - i as f32 / 9.0);
            l.fill_rect(
                Rect::new(cx - 3.5 + i as f32, cy - hh, 1.0, hh * 2.0),
                Color::rgb(255, 255, 255),
            );
        }
    } else {
        l.fill_rect(
            Rect::new(cx - 3.5, cy - 3.5, 7.0, 7.0),
            Color::rgb(255, 255, 255),
        );
    }

    // 状态球小图标
    let icon_size = 18.0f32;
    let icon_x = btn.right() + 12.0;
    let icon_y = (h - icon_size) * 0.5;
    let orb = icon::orb_rgba(p.orb_top, p.orb_bot);
    l.image_pixels(
        &orb,
        (icon::SIZE, icon::SIZE),
        Rect::new(icon_x, icon_y, icon_size, icon_size),
        IMAGE_FIT_COVER,
    );

    // 中：居中的时间
    let clock_w = 60.0f32;
    let clock_x = (w - clock_w) * 0.5;
    l.text(
        hm,
        Rect::new(clock_x, (h - 18.0) * 0.5, clock_w, 18.0),
        15.0,
        700,
        ALIGN_CENTER,
        p.on,
        FONT_NUM,
    );

    // 右：控制模式标签（垂直居中，右对齐）
    let badge = match kind {
        Kind::Autopilot => "Autopilot",
        Kind::Active => "Automatic Controlling",
        _ => "Human Controlling",
    };
    let badge_color = match kind {
        Kind::Autopilot => Color::rgb(0xC4, 0xB0, 0xFF),
        Kind::Active => Color::rgb(0x3E, 0xE8, 0x74),
        _ => Color::rgb(0x53, 0x9C, 0xFF),
    };
    let badge_w = est_width(badge, 10.0);
    l.text(
        badge,
        Rect::new(w - 16.0 - badge_w, (h - 13.0) * 0.5, badge_w + 4.0, 13.0),
        10.0,
        600,
        ALIGN_LEFT,
        badge_color,
        FONT_UI,
    );

    // 左中：目标 / 当前操作
    let text_x = icon_x + icon_size + 10.0;
    let text_w = (clock_x - 14.0 - text_x).max(80.0);
    l.text(
        &headline,
        Rect::new(text_x, 1.0, text_w, 18.0),
        12.0,
        600,
        ALIGN_LEFT,
        p.on,
        FONT_UI,
    );
    l.text(
        &detail,
        Rect::new(text_x, 18.0, text_w, 14.0),
        10.0,
        400,
        ALIGN_LEFT,
        p.sub,
        FONT_UI,
    );

    l.pop_clip();
    l
}

// ---------------------------------------------------------------- 宿主调用

unsafe fn read_table<T: Copy>(
    query: unsafe extern "C" fn(*mut c_void, u32, u32) -> *const c_void,
    context: *mut c_void,
    iface: u32,
) -> Option<T> {
    let p = query(context, iface, IFACE_VERSION_1);
    if p.is_null() {
        None
    } else {
        Some(ptr::read_unaligned(p as *const T))
    }
}

fn surface_size(st: &State, widget: WidgetId, fallback: (f32, f32)) -> (f32, f32) {
    if let Some(f) = st.surface_api.logical_size {
        let mut w = 0.0f32;
        let mut h = 0.0f32;
        let rc = unsafe {
            f(
                st.surface_api.prefix.context,
                st.token,
                widget,
                &mut w,
                &mut h,
            )
        };
        if rc == STATUS_OK && w > 1.0 && h > 1.0 {
            return (w, h);
        }
    }
    fallback
}

fn register_regions(st: &State, widget: WidgetId, rect: Rect) -> i32 {
    let Some(api) = st.input_api else { return -1 };
    let Some(f) = api.set_regions else { return -1 };
    let region = InputRegionV2 {
        id: BTN_ID,
        x: rect.x,
        y: rect.y,
        width: rect.w,
        height: rect.h,
        flags: INPUT_POINTER,
        reserved: 0,
    };
    unsafe { f(api.prefix.context, st.token, widget, &region, 1) }
}

fn activity_spec(st: &State, priority: u32, keep_visible: bool) -> ActivitySpecV2 {
    ActivitySpecV2 {
        struct_size: std::mem::size_of::<ActivitySpecV2>() as u32,
        flags: ACTIVITY_ENABLED
            | if keep_visible {
                ACTIVITY_KEEP_VISIBLE
            } else {
                0
            },
        priority,
        timeout_ms: 0,
        compact_surface: st.compact,
        expanded_page: 0,
        preferred_width: COMPACT_W,
        preferred_height: COMPACT_H,
    }
}

fn update_activity(st: &State, priority: u32, keep_visible: bool) {
    if st.activity == 0 {
        return;
    }
    let Some(api) = st.activity_api else { return };
    let Some(f) = api.update else { return };
    let spec = activity_spec(st, priority, keep_visible);
    unsafe {
        f(api.prefix.context, st.token, st.activity, &spec);
    }
}

fn submit(st: &State, widget: WidgetId, bytes: &[u8]) {
    let Some(f) = st.surface_api.submit_draw_list else { return };
    unsafe {
        f(
            st.surface_api.prefix.context,
            st.token,
            widget,
            bytes.as_ptr(),
            bytes.len() as u32,
        );
    }
}

const WEEKDAYS: [&str; 7] = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

fn local_now(st: &State) -> (String, String) {
    if let Some(api) = st.system_api {
        if let Some(f) = api.local_datetime {
            let mut dt = LocalDateTimeV2 {
                struct_size: std::mem::size_of::<LocalDateTimeV2>() as u32,
                ..Default::default()
            };
            let rc = unsafe { f(api.prefix.context, st.token, &mut dt) };
            if rc == STATUS_OK && dt.year >= 1970 {
                let wd = WEEKDAYS[(dt.day_of_week as usize).min(6)];
                return (
                    format!("{:02}:{:02}:{:02}", dt.hour, dt.minute, dt.second),
                    format!("{}月{:02}日 {}", dt.month, dt.day, wd),
                );
            }
        }
    }
    ("--:--:--".into(), "日期未知".into())
}

fn phase_now() -> f32 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.subsec_millis() as f32 / 1000.0)
        .unwrap_or(0.0)
}

// ---------------------------------------------------------------- 绘制线程

fn worker(st: &'static State) {
    let mut status = client::fetch_status();
    let mut fetched = Instant::now();
    let mut last_activity: Option<(u32, bool)> = None;

    while !st.shutdown.load(Ordering::SeqCst) {
        // 岛内按钮点击 / 热键 → 急停；已停止时再点 → 解除急停恢复
        if st.stop_press.swap(false, Ordering::SeqCst) {
            if status.stopped && !status.active {
                client::clear_stop();
            } else {
                client::post_stop();
            }
            std::thread::sleep(Duration::from_millis(150));
            status = client::fetch_status();
            fetched = Instant::now();
        }

        if fetched.elapsed() >= Duration::from_millis(2000) {
            status = client::fetch_status();
            fetched = Instant::now();
        }

        // 仅在状态变化时更新活动：避免反复刷新把岛钉在展开/常显状态
        let priority = if status.active {
            PRIORITY_HIGH
        } else {
            PRIORITY_MEDIUM
        };
        let keep_visible = status.active;
        let key = (priority, keep_visible);
        if last_activity != Some(key) {
            update_activity(st, priority, keep_visible);
            last_activity = Some(key);
        }

        let (clock, _date) = local_now(st);
        let hm = &clock[..5.min(clock.len())];

        let (cw, ch) = surface_size(st, st.compact, (COMPACT_W, COMPACT_H));
        submit(st, st.compact, render_compact(&status, cw, ch, hm, phase_now()).bytes());
        register_regions(st, st.compact, compact_button(cw, ch));

        let wait_ms = if status.active {
            250
        } else if status.stopped {
            500
        } else {
            900
        };
        let deadline = Instant::now() + Duration::from_millis(wait_ms);
        while Instant::now() < deadline {
            if st.shutdown.load(Ordering::SeqCst) {
                break;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
    }
}

// ---------------------------------------------------------------- 事件回调

unsafe extern "C" fn on_input(_data: *mut c_void, event: *const PluginEventV2) {
    if event.is_null() {
        return;
    }
    let ev = &*event;
    if ev.kind != EVENT_INPUT || ev.detail != INPUT_UP {
        return;
    }
    let st = STATE.load(Ordering::Acquire);
    if st.is_null() {
        return;
    }
    let st = &*st;
    if ev.target != st.compact {
        return;
    }
    let (w, h) = surface_size(st, st.compact, (COMPACT_W, COMPACT_H));
    let rect = compact_button(w, h);

    if ev.x >= rect.x && ev.x <= rect.right() && ev.y >= rect.y && ev.y <= rect.bottom() {
        st.stop_press.store(true, Ordering::SeqCst);
    }
}

unsafe extern "C" fn on_stop_command(_data: *mut c_void, _event: *const PluginEventV2) {
    let st = STATE.load(Ordering::Acquire);
    if !st.is_null() {
        (*st).stop_press.store(true, Ordering::SeqCst);
    }
}

// ---------------------------------------------------------------- 生命周期

unsafe fn create_surface(
    api: &SurfaceApiV2,
    token: PluginToken,
    kind: u32,
    w: f32,
    h: f32,
    key: &str,
    title: &str,
) -> Option<WidgetId> {
    let f = api.create?;
    let spec = SurfaceSpecV2::new(kind, w, h, key, title);
    let mut id: WidgetId = 0;
    if f(api.prefix.context, token, &spec, &mut id) == STATUS_OK && id != 0 {
        Some(id)
    } else {
        None
    }
}

unsafe extern "C" fn create(info: *const PluginCreateInfoV2, out_handle: *mut *mut c_void) -> i32 {
    if info.is_null() || out_handle.is_null() {
        return 1;
    }
    let info = &*info;
    if info.host_api.is_null() {
        return 1;
    }
    let host = &*info.host_api;
    let Some(query) = host.query else {
        return 1;
    };

    let Some(surface_api) = read_table::<SurfaceApiV2>(query, host.prefix.context, IFACE_SURFACE)
    else {
        return 1;
    };

    let Some(compact) = create_surface(
        &surface_api,
        info.plugin_token,
        SURFACE_COMPACT_MAIN,
        COMPACT_W,
        COMPACT_H,
        SURFACE_KEY,
        "Aize 桌面控制",
    ) else {
        return 2;
    };

    let activity_api = read_table::<ActivityApiV2>(query, host.prefix.context, IFACE_ACTIVITY);
    let input_api = read_table::<InputApiV2>(query, host.prefix.context, IFACE_INPUT);
    let events_api = read_table::<EventsApiV2>(query, host.prefix.context, IFACE_EVENTS);
    let system_api = read_table::<SystemApiV2>(query, host.prefix.context, IFACE_SYSTEM);
    let command_api = read_table::<CommandApiV2>(query, host.prefix.context, IFACE_COMMAND);

    let mut state = Box::new(State {
        token: info.plugin_token,
        surface_api,
        activity_api,
        input_api,
        events_api,
        system_api,
        command_api,
        compact,
        activity: 0,
        event_sub: 0,
        cmd: 0,
        shutdown: AtomicBool::new(false),
        stop_press: AtomicBool::new(false),
        worker: Mutex::new(None),
    });

    // 活动（决定收起态宽度与展开页）
    if let Some(api) = activity_api {
        if let Some(f) = api.create {
            let spec = ActivitySpecV2 {
                struct_size: std::mem::size_of::<ActivitySpecV2>() as u32,
                flags: ACTIVITY_ENABLED,
                priority: PRIORITY_MEDIUM,
                timeout_ms: 0,
                compact_surface: compact,
                expanded_page: 0,
                preferred_width: COMPACT_W,
                preferred_height: COMPACT_H,
            };
            let mut id: ResourceId = 0;
            if f(api.prefix.context, info.plugin_token, &spec, &mut id) == STATUS_OK {
                state.activity = id;
            }
        }
    }

    // 订阅胶囊内的指针事件
    if let Some(api) = events_api {
        if let Some(f) = api.subscribe {
            let spec = EventSubscriptionV2 {
                struct_size: std::mem::size_of::<EventSubscriptionV2>() as u32,
                reserved: 0,
                events: EVENT_INPUT,
                target: compact,
                callback: Some(on_input),
                callback_data: ptr::null_mut(),
            };
            let mut id: ResourceId = 0;
            if f(api.prefix.context, info.plugin_token, &spec, &mut id) == STATUS_OK {
                state.event_sub = id;
            }
        }
    }

    // 键盘兜底热键（不进托盘菜单）
    if let Some(api) = command_api {
        if let Some(f) = api.register {
            let spec = CommandSpecV2 {
                struct_size: std::mem::size_of::<CommandSpecV2>() as u32,
                flags: COMMAND_ENABLED,
                key: str_to_fixed::<64>("emergency-stop"),
                title: str_to_fixed::<256>("紧急停止 Aize 桌面控制"),
                hotkey_modifiers: MOD_CONTROL | MOD_ALT | MOD_SHIFT,
                hotkey_key: 0x53, // 'S'
                callback: Some(on_stop_command),
                callback_data: ptr::null_mut(),
            };
            let mut id: ResourceId = 0;
            if f(api.prefix.context, info.plugin_token, &spec, &mut id) == STATUS_OK {
                state.cmd = id;
            }
        }
    }

    let state_ptr = Box::into_raw(state);
    let st: &'static State = &*state_ptr;
    STATE.store(state_ptr, Ordering::Release);

    register_regions(st, compact, compact_button(COMPACT_W, COMPACT_H));

    let handle = std::thread::spawn(move || worker(st));
    if let Ok(mut slot) = st.worker.lock() {
        *slot = Some(handle);
    }

    *out_handle = state_ptr as *mut c_void;
    STATUS_OK
}

unsafe extern "C" fn shutdown(handle: *mut c_void) -> i32 {
    if handle.is_null() {
        return STATUS_OK;
    }
    let st = &*(handle as *const State);
    st.shutdown.store(true, Ordering::SeqCst);
    if let Ok(mut slot) = st.worker.lock() {
        if let Some(t) = slot.take() {
            let _ = t.join();
        }
    }
    STATE.store(ptr::null_mut(), Ordering::Release);

    if let Some(api) = st.events_api {
        if st.event_sub != 0 {
            if let Some(f) = api.release {
                f(api.prefix.context, st.token, st.event_sub);
            }
        }
    }
    if let Some(api) = st.command_api {
        if st.cmd != 0 {
            if let Some(f) = api.release {
                f(api.prefix.context, st.token, st.cmd);
            }
        }
    }
    if let Some(api) = st.activity_api {
        if st.activity != 0 {
            if let Some(f) = api.release {
                f(api.prefix.context, st.token, st.activity);
            }
        }
    }
    if st.compact != 0 {
        if let Some(f) = st.surface_api.release {
            f(st.surface_api.prefix.context, st.token, st.compact);
        }
    }
    STATUS_OK
}

unsafe extern "C" fn destroy(handle: *mut c_void) {
    if !handle.is_null() {
        drop(Box::from_raw(handle as *mut State));
    }
}

// ---------------------------------------------------------------- 描述符

static DESCRIPTOR: PluginDescriptorV2 = PluginDescriptorV2 {
    struct_size: std::mem::size_of::<PluginDescriptorV2>() as u32,
    abi_version: ABI_VERSION_2,
    capabilities: CAP_SURFACE
        | CAP_ACTIVITY
        | CAP_INPUT
        | CAP_EVENTS
        | CAP_SYSTEM
        | CAP_COMMAND,
    metadata: PluginMetadataC {
        id: str_to_fixed::<64>("aize-status"),
        name: str_to_fixed::<128>("Aize Status"),
        version: str_to_fixed::<32>("0.6.2"),
        author: str_to_fixed::<128>("Humanaize"),
        description: str_to_fixed::<256>(
            "纯黑胶囊：时间居中，Aize 目标、当前操作、控制模式与急停",
        ),
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
