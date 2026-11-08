//! 状态头像：代码生成的 RGBA 像素球（渐变球体 + 高光 + 白环 + "A" 徽记）。

pub const SIZE: u32 = 56;

pub fn orb_rgba(top: (u8, u8, u8), bottom: (u8, u8, u8)) -> Vec<u8> {
    let n = SIZE;
    let half = n as f32 / 2.0;
    let radius = half - 2.0;
    let mut out = vec![0u8; (n * n * 4) as usize];

    let (tr, tg, tb) = (top.0 as f32, top.1 as f32, top.2 as f32);
    let (br, bg, bb) = (bottom.0 as f32, bottom.1 as f32, bottom.2 as f32);

    for y in 0..n {
        for x in 0..n {
            let px = x as f32 + 0.5;
            let py = y as f32 + 0.5;
            let u = (px - half) / radius;
            let v = (py - half) / radius;
            let d = (u * u + v * v).sqrt();

            let coverage = smoothstep(1.02, 0.96, d);
            if coverage <= 0.0 {
                continue;
            }

            // 球体径向渐变（左上亮 → 右下暗）
            let t = (((u + v) * 0.5 + 1.0) * 0.5).clamp(0.0, 1.0);
            let mut r = tr + (br - tr) * t;
            let mut g = tg + (bg - tg) * t;
            let mut b = tb + (bb - tb) * t;

            // 顶部环境光
            let hi = smoothstep(0.55, 0.0, ((u + 0.05).powi(2) + (v + 0.45).powi(2)).sqrt()) * 0.22;
            r += (255.0 - r) * hi;
            g += (255.0 - g) * hi;
            b += (255.0 - b) * hi;

            // 白色内环
            let ring = band(d, 0.80, 0.92);
            let k = ring * 0.55;
            r += (255.0 - r) * k;
            g += (255.0 - g) * k;
            b += (255.0 - b) * k;

            // 左上高光椭圆
            let ex = (u + 0.30) / 0.42;
            let ey = (v + 0.36) / 0.20;
            let gloss = smoothstep(1.0, 0.35, (ex * ex + ey * ey).sqrt()) * 0.40;
            r += (255.0 - r) * gloss;
            g += (255.0 - g) * gloss;
            b += (255.0 - b) * gloss;

            // "A" 徽记（三条线段）
            let a = seg_dist(u, v, -0.42, 0.44, 0.0, -0.46)
                .min(seg_dist(u, v, 0.42, 0.44, 0.0, -0.46))
                .min(seg_dist(u, v, -0.22, 0.08, 0.24, 0.08));
            let glyph = smoothstep(0.105, 0.055, a) * 0.92;
            r += (255.0 - r) * glyph;
            g += (255.0 - g) * glyph;
            b += (255.0 - b) * glyph;

            let alpha = (coverage * 255.0) as u8;
            let idx = ((y * n + x) * 4) as usize;
            out[idx] = r.clamp(0.0, 255.0) as u8;
            out[idx + 1] = g.clamp(0.0, 255.0) as u8;
            out[idx + 2] = b.clamp(0.0, 255.0) as u8;
            out[idx + 3] = alpha;
        }
    }
    out
}

fn smoothstep(edge0: f32, edge1: f32, x: f32) -> f32 {
    if edge0 == edge1 {
        return if x < edge0 { 0.0 } else { 1.0 };
    }
    let t = ((x - edge0) / (edge1 - edge0)).clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}

/// d 落在 [lo, hi] 区间内的软边遮罩（1 = 区间内）
fn band(d: f32, lo: f32, hi: f32) -> f32 {
    smoothstep(lo - 0.03, lo + 0.03, d) * smoothstep(hi + 0.03, hi - 0.03, d)
}

fn seg_dist(px: f32, py: f32, ax: f32, ay: f32, bx: f32, by: f32) -> f32 {
    let vx = bx - ax;
    let vy = by - ay;
    let wx = px - ax;
    let wy = py - ay;
    let c2 = vx * vx + vy * vy;
    let t = if c2 > 0.0 {
        ((wx * vx + wy * vy) / c2).clamp(0.0, 1.0)
    } else {
        0.0
    };
    let dx = wx - t * vx;
    let dy = wy - t * vy;
    (dx * dx + dy * dy).sqrt()
}
