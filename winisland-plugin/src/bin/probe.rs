//! probe —— 命令行验证 Aize 状态端点解析是否正确。
//! 用法: probe [port]

use aize_status::client;

fn main() {
    let port: u16 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(8082);
    println!("GET http://127.0.0.1:{}/api/desktop-control/status", port);
    let st = client::fetch_status(port);
    println!("{:#?}", st);

    if std::env::var("PROBE_STOP").is_ok() {
        let ok = client::post_stop(port);
        println!("POST /api/desktop-control/stop -> {}", ok);
    }
}
