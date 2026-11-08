//! DrawList v2 线协议构建器（零依赖，纯手写，格式与宿主一致）。

pub const MAGIC: u32 = 0x5749_4432;
pub const VERSION: u32 = 2;

pub const PUSH_CLIP_ROUND_RECT: u16 = 0x0002;
pub const POP_CLIP: u16 = 0x0003;
pub const PUSH_ALPHA: u16 = 0x0006;
pub const POP_ALPHA: u16 = 0x0007;
pub const FILL_RECT: u16 = 0x0010;
pub const FILL_ROUND_RECT: u16 = 0x0011;
pub const FILL_CIRCLE: u16 = 0x0012;
pub const FILL_LINEAR_GRADIENT: u16 = 0x0014;
pub const STROKE_LINE: u16 = 0x0020;
pub const STROKE_ROUND_RECT: u16 = 0x0021;
pub const STROKE_ARC: u16 = 0x0022;
pub const DRAW_IMAGE_PIXELS: u16 = 0x0031;
pub const DRAW_TEXT: u16 = 0x0040;
pub const DRAW_SHADOW_ROUND_RECT: u16 = 0x0050;

/// 0 = 左对齐，1 = 居中，2 = 右对齐
pub const ALIGN_LEFT: u8 = 0;
pub const ALIGN_CENTER: u8 = 1;
pub const ALIGN_RIGHT: u8 = 2;

#[derive(Clone, Copy)]
pub struct Rect {
    pub x: f32,
    pub y: f32,
    pub w: f32,
    pub h: f32,
}

impl Rect {
    pub const fn new(x: f32, y: f32, w: f32, h: f32) -> Self {
        Self { x, y, w, h }
    }
    pub fn right(&self) -> f32 {
        self.x + self.w
    }
    pub fn bottom(&self) -> f32 {
        self.y + self.h
    }
}

/// 0xAARRGGBB
#[derive(Clone, Copy, PartialEq)]
pub struct Color(pub u32);

impl Color {
    pub const fn rgb(r: u8, g: u8, b: u8) -> Self {
        Self(0xFF00_0000 | ((r as u32) << 16) | ((g as u32) << 8) | (b as u32))
    }
    pub const fn rgba(r: u8, g: u8, b: u8, a: u8) -> Self {
        Self(((a as u32) << 24) | ((r as u32) << 16) | ((g as u32) << 8) | (b as u32))
    }
    pub const fn argb(v: u32) -> Self {
        Self(v)
    }
    pub const fn alpha(self, a: u8) -> Self {
        Self((self.0 & 0x00ff_ffff) | ((a as u32) << 24))
    }
    pub const fn rgb_only(self) -> u32 {
        self.0 & 0x00ff_ffff
    }
    /// t=0 取 self，t=1 取 other（含 alpha）
    pub fn mix(self, other: Color, t: f32) -> Color {
        let t = t.clamp(0.0, 1.0);
        let a0 = (self.0 >> 24) & 0xff;
        let r0 = (self.0 >> 16) & 0xff;
        let g0 = (self.0 >> 8) & 0xff;
        let b0 = self.0 & 0xff;
        let a1 = (other.0 >> 24) & 0xff;
        let r1 = (other.0 >> 16) & 0xff;
        let g1 = (other.0 >> 8) & 0xff;
        let b1 = other.0 & 0xff;
        let lerp = |x: u32, y: u32| ((x as f32) * (1.0 - t) + (y as f32) * t) as u32;
        Color::argb(
            (lerp(a0, a1) << 24) | (lerp(r0, r1) << 16) | (lerp(g0, g1) << 8) | lerp(b0, b1),
        )
    }
}

pub struct List {
    bytes: Vec<u8>,
    count: u32,
}

impl List {
    pub fn new(width: f32, height: f32) -> Self {
        let mut bytes = Vec::with_capacity(1024);
        bytes.extend_from_slice(&MAGIC.to_le_bytes());
        bytes.extend_from_slice(&VERSION.to_le_bytes());
        bytes.extend_from_slice(&width.to_le_bytes());
        bytes.extend_from_slice(&height.to_le_bytes());
        bytes.extend_from_slice(&0u32.to_le_bytes());
        bytes.extend_from_slice(&0u32.to_le_bytes());
        Self { bytes, count: 0 }
    }

    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }

    pub fn commands(&self) -> u32 {
        self.count
    }

    fn cmd(&mut self, opcode: u16, payload: &[u8]) -> &mut Self {
        self.bytes.extend_from_slice(&opcode.to_le_bytes());
        self.bytes.extend_from_slice(&0u16.to_le_bytes());
        self.bytes
            .extend_from_slice(&(payload.len() as u32).to_le_bytes());
        self.bytes.extend_from_slice(payload);
        self.count = self.count.saturating_add(1);
        self.bytes[16..20].copy_from_slice(&self.count.to_le_bytes());
        let total = (self.bytes.len() - 24) as u32;
        self.bytes[20..24].copy_from_slice(&total.to_le_bytes());
        self
    }

    pub fn clip_round(&mut self, rect: Rect, radius: f32) -> &mut Self {
        let mut p = rect_bytes(rect);
        push_f32(&mut p, radius);
        self.cmd(PUSH_CLIP_ROUND_RECT, &p)
    }

    pub fn pop_clip(&mut self) -> &mut Self {
        self.cmd(POP_CLIP, &[])
    }

    pub fn alpha(&mut self, value: u8) -> &mut Self {
        self.cmd(PUSH_ALPHA, &[value])
    }

    pub fn pop_alpha(&mut self) -> &mut Self {
        self.cmd(POP_ALPHA, &[])
    }

    pub fn fill_rect(&mut self, rect: Rect, color: Color) -> &mut Self {
        let mut p = rect_bytes(rect);
        push_u32(&mut p, color.0);
        self.cmd(FILL_RECT, &p)
    }

    pub fn fill_round_rect(&mut self, rect: Rect, radius: f32, color: Color) -> &mut Self {
        let mut p = rect_bytes(rect);
        push_f32(&mut p, radius);
        push_u32(&mut p, color.0);
        self.cmd(FILL_ROUND_RECT, &p)
    }

    pub fn fill_circle(&mut self, x: f32, y: f32, radius: f32, color: Color) -> &mut Self {
        let mut p = Vec::with_capacity(16);
        push_f32(&mut p, x);
        push_f32(&mut p, y);
        push_f32(&mut p, radius);
        push_u32(&mut p, color.0);
        self.cmd(FILL_CIRCLE, &p)
    }

    pub fn fill_gradient(&mut self, rect: Rect, angle_deg: f32, stops: &[(f32, Color)]) -> &mut Self {
        let mut p = rect_bytes(rect);
        push_f32(&mut p, angle_deg);
        p.push(stops.len().min(255) as u8);
        for &(pos, color) in stops {
            push_f32(&mut p, pos);
            push_u32(&mut p, color.0);
        }
        self.cmd(FILL_LINEAR_GRADIENT, &p)
    }

    pub fn stroke_line(&mut self, from: (f32, f32), to: (f32, f32), width: f32, color: Color) -> &mut Self {
        let mut p = Vec::with_capacity(24);
        for v in [from.0, from.1, to.0, to.1, width] {
            push_f32(&mut p, v);
        }
        push_u32(&mut p, color.0);
        self.cmd(STROKE_LINE, &p)
    }

    pub fn stroke_round_rect(&mut self, rect: Rect, radius: f32, width: f32, color: Color) -> &mut Self {
        let mut p = rect_bytes(rect);
        push_f32(&mut p, radius);
        push_f32(&mut p, width);
        push_u32(&mut p, color.0);
        self.cmd(STROKE_ROUND_RECT, &p)
    }

    pub fn stroke_arc(&mut self, rect: Rect, start: f32, sweep: f32, width: f32, color: Color) -> &mut Self {
        let mut p = rect_bytes(rect);
        for v in [start, sweep, width] {
            push_f32(&mut p, v);
        }
        push_u32(&mut p, color.0);
        self.cmd(STROKE_ARC, &p)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn text(
        &mut self,
        value: &str,
        rect: Rect,
        size: f32,
        weight: u16,
        align: u8,
        color: Color,
        family: &str,
    ) -> &mut Self {
        let mut p = rect_bytes(rect);
        push_u32(&mut p, value.len() as u32);
        p.extend_from_slice(value.as_bytes());
        push_f32(&mut p, size);
        push_u16(&mut p, weight);
        p.extend_from_slice(&[0u8, align, 0u8, 1u8]); // italic / align / wrap / ellipsis
        push_family(&mut p, family);
        push_u32(&mut p, color.0);
        self.cmd(DRAW_TEXT, &p)
    }

    pub fn image_pixels(
        &mut self,
        rgba: &[u8],
        (img_w, img_h): (u32, u32),
        rect: Rect,
        fit: u8,
    ) -> &mut Self {
        let mut p = rect_bytes(rect);
        p.extend_from_slice(&[fit, 255u8]);
        push_u32(&mut p, img_w);
        push_u32(&mut p, img_h);
        push_u32(&mut p, rgba.len() as u32);
        p.extend_from_slice(rgba);
        self.cmd(DRAW_IMAGE_PIXELS, &p)
    }

    pub fn shadow_round_rect(
        &mut self,
        rect: Rect,
        radius: f32,
        sigma: f32,
        offset: (f32, f32),
        color: Color,
    ) -> &mut Self {
        let mut p = rect_bytes(rect);
        for v in [radius, sigma, offset.0, offset.1] {
            push_f32(&mut p, v);
        }
        push_u32(&mut p, color.0);
        self.cmd(DRAW_SHADOW_ROUND_RECT, &p)
    }
}

fn rect_bytes(rect: Rect) -> Vec<u8> {
    let mut p = Vec::with_capacity(16);
    for v in [rect.x, rect.y, rect.w, rect.h] {
        push_f32(&mut p, v);
    }
    p
}

fn push_family(bytes: &mut Vec<u8>, family: &str) {
    let mut len = family.len().min(255);
    while len > 0 && !family.is_char_boundary(len) {
        len -= 1;
    }
    push_u16(bytes, len as u16);
    bytes.extend_from_slice(&family.as_bytes()[..len]);
}

fn push_u16(bytes: &mut Vec<u8>, v: u16) {
    bytes.extend_from_slice(&v.to_le_bytes());
}

fn push_u32(bytes: &mut Vec<u8>, v: u32) {
    bytes.extend_from_slice(&v.to_le_bytes());
}

fn push_f32(bytes: &mut Vec<u8>, v: f32) {
    bytes.extend_from_slice(&v.to_le_bytes());
}
