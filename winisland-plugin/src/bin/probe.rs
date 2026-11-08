//! probe —— 命令行验证 Aize 桌面控制状态（文件态）解析是否正确。

use aize_status::client;

fn main() {
    let st = client::fetch_status();
    println!("{:#?}", st);

    if std::env::var("PROBE_STOP").is_ok() {
        let ok = client::post_stop();
        println!("write desktop_control.stop -> {}", ok);
    }
}
