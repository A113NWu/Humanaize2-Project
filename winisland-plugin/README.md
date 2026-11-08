# Aize Status for WinIsland

在 WinIsland 顶部胶囊里显示 Aize 的运行状态：

- 当前目标与正在执行的操作
- 右侧模式标签：`Human Controlling`（蓝）/ `Automatic Controlling`（绿）/ `Autopilot`（紫）
- 中间时间
- 纯黑胶囊，自动缩回

## 数据来源

插件读取 Humanaize2 写出的状态文件 `desktop_control_state.json`（依次尝试）：

1. `D:\Program Files\Humanaize2-x64\data\`
2. `C:\Program Files\Humanaize2-x64\data\`
3. `%USERPROFILE%\.humanaize2\data\`
4. 源码仓库的 `data/`

文件由 `computer-control` 技能在每次动作时写入；单步动作状态 6 秒过期，Autopilot 状态 600 秒过期。

## 安装

把 `plugin.yml`、`aize_status.dll`、`icon.png`、`README.md` 放进：

```
%APPDATA%\WinIsland\plugins\aize-status\
```

然后在 WinIsland 插件列表里选中 **Aize Status**。

## 构建

```bash
cd winisland-plugin
cargo build --release
# 产物：target\release\aize_status.dll
```

需要 Rust stable（MSVC 工具链）与 Windows SDK。
