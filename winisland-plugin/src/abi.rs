//! WinIsland 插件 ABI v2 类型定义（内联自 winisland-plugin-api 0.11.0 的 C 表布局）。
//!
//! 布局必须与宿主完全一致（均为 #[repr(C)]，字段顺序不可调整）。

#![allow(non_snake_case)]
use std::ffi::c_void;

pub const ABI_VERSION_2: u32 = 2;
pub const IFACE_CONTEXT: u32 = 0x01;
pub const IFACE_MEDIA: u32 = 0x02;
pub const IFACE_I18N: u32 = 0x03;
pub const IFACE_HOST_STATE: u32 = 0x04;
pub const IFACE_WIDGET: u32 = 0x05;
pub const IFACE_TEXT: u32 = 0x08;
pub const IFACE_IMAGE: u32 = 0x09;
pub const IFACE_LOG: u32 = 0x0b;
pub const IFACE_INPUT: u32 = 0x0c;
pub const IFACE_COMMAND: u32 = 0x0d;
pub const IFACE_SURFACE: u32 = 0x0e;
pub const IFACE_EVENTS: u32 = 0x0f;
pub const IFACE_SYSTEM: u32 = 0x11;
pub const IFACE_ACTIVITY: u32 = 0x12;
pub const IFACE_VERSION_1: u32 = 1;

pub const CAP_CONTEXT: u64 = 1 << 0;
pub const CAP_TEXT: u64 = 1 << 7;
pub const CAP_IMAGE: u64 = 1 << 8;
pub const CAP_INPUT: u64 = 1 << 10;
pub const CAP_COMMAND: u64 = 1 << 11;
pub const CAP_SURFACE: u64 = 1 << 12;
pub const CAP_EVENTS: u64 = 1 << 13;
pub const CAP_SYSTEM: u64 = 1 << 15;
pub const CAP_ACTIVITY: u64 = 1 << 16;

pub const PRIORITY_LOW: u32 = 0;
pub const PRIORITY_MEDIUM: u32 = 1;
pub const PRIORITY_HIGH: u32 = 2;

pub const CONTEXT_FLAG_SHOW_COMPACT: u32 = 1 << 0;

pub const COMMAND_ENABLED: u32 = 1;
pub const COMMAND_TRAY: u32 = 2;
pub const MOD_CONTROL: u32 = 1;
pub const MOD_ALT: u32 = 2;
pub const MOD_SHIFT: u32 = 4;

pub const EVENT_INPUT: u64 = 1 << 0;
pub const EVENT_RESIZE: u64 = 1 << 4;
pub const INPUT_DOWN: u32 = 2;
pub const INPUT_UP: u32 = 3;
pub const INPUT_POINTER: u32 = 1 << 0;

pub const SURFACE_PAGE: u32 = 1;
pub const SURFACE_COMPACT_MAIN: u32 = 6;
pub const SURFACE_ENABLED: u32 = 1;
pub const ACTIVITY_ENABLED: u32 = 1;
pub const ACTIVITY_KEEP_VISIBLE: u32 = 2;

pub const IMAGE_FIT_COVER: u8 = 1;

pub type PluginToken = u64;
pub type ResourceId = u64;
pub type WidgetId = u64;
pub type ImageId = u64;
pub type PluginStatus = i32;

pub const STATUS_OK: i32 = 0;

pub const fn str_to_fixed<const N: usize>(s: &str) -> [u8; N] {
    let mut buf = [0u8; N];
    let bytes = s.as_bytes();
    let len = if bytes.len() < N { bytes.len() } else { N - 1 };
    let mut i = 0;
    while i < len {
        buf[i] = bytes[i];
        i += 1;
    }
    buf
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct TablePrefix {
    pub struct_size: u32,
    pub version: u32,
    pub context: *mut c_void,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct PluginHostV2 {
    pub prefix: TablePrefix,
    pub host_build: u32,
    pub query: Option<unsafe extern "C" fn(*mut c_void, u32, u32) -> *const c_void>,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct PluginCreateInfoV2 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub plugin_token: PluginToken,
    pub host_api: *const PluginHostV2,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct PluginMetadataC {
    pub id: [u8; 64],
    pub name: [u8; 128],
    pub version: [u8; 32],
    pub author: [u8; 128],
    pub description: [u8; 256],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Utf8Slice {
    pub ptr: *const u8,
    pub len: u32,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct ByteSlice {
    pub ptr: *const u8,
    pub len: u32,
}

// ---------------------------------------------------------------- context

#[repr(C)]
#[derive(Clone, Copy)]
pub struct ContextDataV2 {
    pub struct_size: u32,
    pub priority: u32,
    pub flags: u32,
    pub timeout_ms: u32,
    pub title: [u8; 256],
    pub body: [u8; 512],
    pub compact_text: [u8; 128],
}

impl ContextDataV2 {
    pub fn new(priority: u32, title: &str, body: &str, compact: &str) -> Self {
        Self {
            struct_size: std::mem::size_of::<Self>() as u32,
            priority,
            flags: CONTEXT_FLAG_SHOW_COMPACT,
            timeout_ms: 0,
            title: str_to_fixed::<256>(title),
            body: str_to_fixed::<512>(body),
            compact_text: str_to_fixed::<128>(compact),
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct ContextApiV2 {
    pub prefix: TablePrefix,
    pub create: Option<
        unsafe extern "C" fn(*mut c_void, PluginToken, *const ContextDataV2, *mut ResourceId) -> i32,
    >,
    pub update: Option<
        unsafe extern "C" fn(*mut c_void, PluginToken, ResourceId, *const ContextDataV2) -> i32,
    >,
    pub release: Option<unsafe extern "C" fn(*mut c_void, PluginToken, ResourceId) -> i32>,
}

// ---------------------------------------------------------------- surface / activity

#[repr(C)]
#[derive(Clone, Copy)]
pub struct SurfaceSpecV2 {
    pub struct_size: u32,
    pub kind: u32,
    pub flags: u32,
    pub order: i32,
    pub width: f32,
    pub height: f32,
    pub key: [u8; 64],
    pub title: [u8; 256],
}

impl SurfaceSpecV2 {
    pub fn new(kind: u32, width: f32, height: f32, key: &str, title: &str) -> Self {
        Self {
            struct_size: std::mem::size_of::<Self>() as u32,
            kind,
            flags: SURFACE_ENABLED,
            order: 0,
            width,
            height,
            key: str_to_fixed::<64>(key),
            title: str_to_fixed::<256>(title),
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct SurfaceApiV2 {
    pub prefix: TablePrefix,
    pub create: Option<
        unsafe extern "C" fn(
            *mut c_void,
            PluginToken,
            *const SurfaceSpecV2,
            *mut WidgetId,
        ) -> PluginStatus,
    >,
    pub update: Option<
        unsafe extern "C" fn(
            *mut c_void,
            PluginToken,
            WidgetId,
            *const SurfaceSpecV2,
        ) -> PluginStatus,
    >,
    pub release: Option<unsafe extern "C" fn(*mut c_void, PluginToken, WidgetId) -> PluginStatus>,
    pub submit_draw_list: Option<
        unsafe extern "C" fn(*mut c_void, PluginToken, WidgetId, *const u8, u32) -> PluginStatus,
    >,
    pub logical_size: Option<
        unsafe extern "C" fn(
            *mut c_void,
            PluginToken,
            WidgetId,
            *mut f32,
            *mut f32,
        ) -> PluginStatus,
    >,
    pub show_page: Option<unsafe extern "C" fn(*mut c_void, PluginToken, WidgetId) -> PluginStatus>,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct ActivitySpecV2 {
    pub struct_size: u32,
    pub flags: u32,
    pub priority: u32,
    pub timeout_ms: u32,
    pub compact_surface: WidgetId,
    pub expanded_page: WidgetId,
    pub preferred_width: f32,
    pub preferred_height: f32,
}

impl ActivitySpecV2 {
    pub fn new(
        priority: u32,
        compact_surface: WidgetId,
        preferred_width: f32,
        preferred_height: f32,
    ) -> Self {
        Self {
            struct_size: std::mem::size_of::<Self>() as u32,
            flags: ACTIVITY_ENABLED | ACTIVITY_KEEP_VISIBLE,
            priority,
            timeout_ms: 0,
            compact_surface,
            expanded_page: 0,
            preferred_width,
            preferred_height,
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct ActivityApiV2 {
    pub prefix: TablePrefix,
    pub create: Option<
        unsafe extern "C" fn(
            *mut c_void,
            PluginToken,
            *const ActivitySpecV2,
            *mut ResourceId,
        ) -> PluginStatus,
    >,
    pub update: Option<
        unsafe extern "C" fn(
            *mut c_void,
            PluginToken,
            ResourceId,
            *const ActivitySpecV2,
        ) -> PluginStatus,
    >,
    pub release: Option<unsafe extern "C" fn(*mut c_void, PluginToken, ResourceId) -> PluginStatus>,
}

// ---------------------------------------------------------------- input / events

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct InputRegionV2 {
    pub id: u64,
    pub x: f32,
    pub y: f32,
    pub width: f32,
    pub height: f32,
    pub flags: u32,
    pub reserved: u32,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct InputApiV2 {
    pub prefix: TablePrefix,
    pub set_regions: Option<
        unsafe extern "C" fn(
            *mut c_void,
            PluginToken,
            WidgetId,
            *const InputRegionV2,
            u32,
        ) -> PluginStatus,
    >,
    pub release_capture:
        Option<unsafe extern "C" fn(*mut c_void, PluginToken, WidgetId) -> PluginStatus>,
}

#[repr(C)]
pub struct PluginEventV2 {
    pub struct_size: u32,
    pub detail: u32,
    pub kind: u64,
    pub target: WidgetId,
    pub resource: ResourceId,
    pub sequence: u64,
    pub time_seconds: f64,
    pub x: f32,
    pub y: f32,
    pub delta_x: f32,
    pub delta_y: f32,
    pub modifiers: u32,
    pub code: u32,
    pub data: ByteSlice,
}

pub type PluginEventFnV2 = unsafe extern "C" fn(*mut c_void, *const PluginEventV2);

#[repr(C)]
#[derive(Clone, Copy)]
pub struct EventSubscriptionV2 {
    pub struct_size: u32,
    pub reserved: u32,
    pub events: u64,
    pub target: WidgetId,
    pub callback: Option<PluginEventFnV2>,
    pub callback_data: *mut c_void,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct IslandStateV2 {
    pub struct_size: u32,
    pub expanded: u8,
    pub visible: u8,
    pub light_theme: u8,
    pub reserved: u8,
    pub page: u64,
    pub width: f32,
    pub height: f32,
    pub scale: f32,
    pub reserved2: u32,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct EventsApiV2 {
    pub prefix: TablePrefix,
    pub subscribe: Option<
        unsafe extern "C" fn(
            *mut c_void,
            PluginToken,
            *const EventSubscriptionV2,
            *mut ResourceId,
        ) -> PluginStatus,
    >,
    pub create_timer: Option<
        unsafe extern "C" fn(
            *mut c_void,
            PluginToken,
            *const TimerSpecV2,
            *mut ResourceId,
        ) -> PluginStatus,
    >,
    pub release:
        Option<unsafe extern "C" fn(*mut c_void, PluginToken, ResourceId) -> PluginStatus>,
    pub island_state:
        Option<unsafe extern "C" fn(*mut c_void, PluginToken, *mut IslandStateV2) -> PluginStatus>,
    pub set_animation:
        Option<unsafe extern "C" fn(*mut c_void, PluginToken, WidgetId, u8) -> PluginStatus>,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct TimerSpecV2 {
    pub struct_size: u32,
    pub flags: u32,
    pub delay_ms: u64,
    pub interval_ms: u64,
    pub target: WidgetId,
    pub callback: Option<PluginEventFnV2>,
    pub callback_data: *mut c_void,
}

// ---------------------------------------------------------------- system

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct LocalDateTimeV2 {
    pub struct_size: u32,
    pub year: u16,
    pub month: u16,
    pub day: u16,
    pub day_of_week: u16,
    pub hour: u16,
    pub minute: u16,
    pub second: u16,
    pub millisecond: u16,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct LunarDateV2 {
    pub year: u16,
    pub month: u16,
    pub day: u16,
    pub is_leap_month: u8,
    pub reserved: u8,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct SystemApiV2 {
    pub prefix: TablePrefix,
    pub local_datetime:
        Option<unsafe extern "C" fn(*mut c_void, PluginToken, *mut LocalDateTimeV2) -> PluginStatus>,
    pub lunar_date: Option<
        unsafe extern "C" fn(
            *mut c_void,
            PluginToken,
            u16,
            u16,
            u16,
            *mut LunarDateV2,
            *mut u8,
        ) -> PluginStatus,
    >,
    pub current_language:
        Option<unsafe extern "C" fn(*mut c_void, PluginToken, *mut u8, u32, *mut u32) -> PluginStatus>,
}

// ---------------------------------------------------------------- command

#[repr(C)]
#[derive(Clone, Copy)]
pub struct CommandSpecV2 {
    pub struct_size: u32,
    pub flags: u32,
    pub key: [u8; 64],
    pub title: [u8; 256],
    pub hotkey_modifiers: u32,
    pub hotkey_key: u32,
    pub callback: Option<PluginEventFnV2>,
    pub callback_data: *mut c_void,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct CommandInfoV2 {
    pub struct_size: u32,
    pub flags: u32,
    pub id: [u8; 160],
    pub title: [u8; 256],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct CommandApiV2 {
    pub prefix: TablePrefix,
    pub register:
        Option<unsafe extern "C" fn(*mut c_void, PluginToken, *const CommandSpecV2, *mut ResourceId) -> i32>,
    pub set_enabled: Option<unsafe extern "C" fn(*mut c_void, PluginToken, ResourceId, u8) -> i32>,
    pub list: Option<
        unsafe extern "C" fn(*mut c_void, PluginToken, *mut CommandInfoV2, u32, *mut u32) -> i32,
    >,
    pub execute: Option<
        unsafe extern "C" fn(*mut c_void, PluginToken, Utf8Slice, ByteSlice, *mut u64) -> i32,
    >,
    pub release: Option<unsafe extern "C" fn(*mut c_void, PluginToken, ResourceId) -> i32>,
}

// ---------------------------------------------------------------- descriptor

#[repr(C)]
#[derive(Clone, Copy)]
pub struct PluginDescriptorV2 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub capabilities: u64,
    pub metadata: PluginMetadataC,
    pub create: Option<unsafe extern "C" fn(*const PluginCreateInfoV2, *mut *mut c_void) -> i32>,
    pub shutdown: Option<unsafe extern "C" fn(*mut c_void) -> i32>,
    pub destroy: Option<unsafe extern "C" fn(*mut c_void)>,
    pub on_tick: Option<unsafe extern "C" fn(*mut c_void, WidgetId, f64) -> i32>,
}

// ---------------------------------------------------------------- 布局自检
const _: () = {
    assert!(std::mem::size_of::<TablePrefix>() == 16);
    assert!(std::mem::size_of::<PluginHostV2>() == 32);
    assert!(std::mem::size_of::<PluginCreateInfoV2>() == 24);
    assert!(std::mem::size_of::<PluginMetadataC>() == 608);
    assert!(std::mem::size_of::<PluginDescriptorV2>() == 656);
    assert!(std::mem::size_of::<ContextApiV2>() == 40);
    assert!(std::mem::size_of::<ContextDataV2>() == 912);
    assert!(std::mem::size_of::<CommandApiV2>() == 56);
    assert!(std::mem::size_of::<CommandSpecV2>() == 352);
    assert!(std::mem::size_of::<SurfaceApiV2>() == 64);
    assert!(std::mem::size_of::<SurfaceSpecV2>() == 344);
    assert!(std::mem::size_of::<ActivityApiV2>() == 40);
    assert!(std::mem::size_of::<ActivitySpecV2>() == 40);
    assert!(std::mem::size_of::<InputApiV2>() == 32);
    assert!(std::mem::size_of::<InputRegionV2>() == 32);
    assert!(std::mem::size_of::<PluginEventV2>() == 88);
    assert!(std::mem::size_of::<EventSubscriptionV2>() == 40);
    assert!(std::mem::size_of::<EventsApiV2>() == 56);
    assert!(std::mem::size_of::<SystemApiV2>() == 40);
    assert!(std::mem::size_of::<LocalDateTimeV2>() == 20);
};
