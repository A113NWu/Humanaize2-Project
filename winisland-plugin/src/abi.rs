//! WinIsland 插件 ABI v2 类型定义（内联自 winisland-plugin-api 0.11.0，MIT）。
//!
//! 布局断言摘自 crate 的 abi/layout.rs，必须保持一致。

#![allow(non_snake_case)]
use std::ffi::c_void;

pub const ABI_VERSION_2: u32 = 2;
pub const IFACE_CONTEXT: u32 = 0x01;
pub const IFACE_COMMAND: u32 = 0x0d;
pub const IFACE_VERSION_1: u32 = 1;

pub const CAP_CONTEXT: u64 = 1 << 0;
pub const CAP_COMMAND: u64 = 1 << 11;

pub const PRIORITY_LOW: u32 = 0;
pub const PRIORITY_MEDIUM: u32 = 1;
pub const PRIORITY_HIGH: u32 = 2;

pub const CONTEXT_FLAG_SHOW_COMPACT: u32 = 1 << 0;

pub const COMMAND_ENABLED: u32 = 1;
pub const COMMAND_TRAY: u32 = 2;
pub const MOD_CONTROL: u32 = 1;
pub const MOD_ALT: u32 = 2;
pub const MOD_SHIFT: u32 = 4;

pub type PluginToken = u64;
pub type ResourceId = u64;
pub type WidgetId = u64;

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

/// 命令回调收到的事件结构（本插件不读内容，仅占位）。
#[repr(C)]
pub struct PluginEventV2 {
    _private: [u8; 0],
}

pub type PluginEventFnV2 = unsafe extern "C" fn(*mut c_void, *const PluginEventV2);

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
};
