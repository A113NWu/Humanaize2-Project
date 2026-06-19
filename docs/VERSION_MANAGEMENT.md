# 版本管理系统使用说明

**← [返回主文档](./README.md)** | [📖 文档导航](./README.md)

## 概述

Humanaize 2.0 现在使用统一的版本管理系统，所有版本号都从 `config/version.json` 读取，避免了多处硬编码版本号的问题。

## 版本文件位置

```
config/version.json
```

## 文件格式

```json
{
  "version": "2.2.3",
  "last_updated": "2026-06-16T00:00:00.000000",
  "release_notes": "v2.2.3新增：0.Windows現代化GUI介面..."
}
```

## 使用方法

### 1. 获取版本号

```python
from src.core.version import get_version

version = get_version()
print(f"当前版本: {version}")  # 输出: 当前版本: 2.2.3
```

### 2. 获取完整版本信息

```python
from src.core.version import get_version_info

info = get_version_info()
print(info)
# 输出:
# {
#   'version': '2.2.3',
#   'last_updated': '2026-06-16T00:00:00.000000',
#   'release_notes': 'v2.2.3新增：...'
# }
```

### 3. 获取不同用途的User-Agent

```python
from src.core.version import (
    get_user_agent,
    get_update_checker_agent,
    get_downloader_agent,
    get_model_downloader_agent
)

# 通用User-Agent
print(get_user_agent())              # Humanaize2/2.2.3

# 更新检查器User-Agent
print(get_update_checker_agent())     # Humanaize2-Update-Checker/2.2.3

# 下载器User-Agent
print(get_downloader_agent())        # Humanaize2-Downloader/2.2.3

# 模型下载器User-Agent
print(get_model_downloader_agent())  # Humanaize2-Model-Downloader/2.2.3
```

### 4. 在其他模块中使用

#### AutoUpdater

```python
from src.core.utils.auto_updater import AutoUpdater

# 自动从version.json获取版本号
updater = AutoUpdater('https://api.github.com/repos/A113NWu/Humanaize2-Project/releases')

# 获取本地版本
print(updater.get_local_version())  # 2.2.3
```

#### ModelDownloader

```python
from src.core.llm.model_downloader import ModelDownloader

downloader = ModelDownloader()
# User-Agent会自动使用正确的版本号
```

## 更新版本号

只需修改 `config/version.json` 中的 `version` 字段：

```json
{
  "version": "2.3.0",  // 改成新版本号
  "last_updated": "2026-06-16T00:00:00.000000",
  "release_notes": "v2.3.0 更新内容..."
}
```

所有使用 `get_version()` 或相关函数的地方都会自动使用新版本号。

## 查找所有硬编码版本号

如果需要查找是否还有遗漏的硬编码版本号：

```bash
grep -r "2\.2\.3" src/ --include="*.py" | grep -v version.py
```

## 优势

1. **单一数据源**: 版本号只在一处定义
2. **易于维护**: 只需修改一个文件即可更新所有地方的版本号
3. **减少错误**: 避免因遗漏导致版本号不一致的问题
4. **灵活查找**: 可以快速定位所有使用版本号的地方

## 注意事项

- 版本管理系统会缓存版本号，如果修改了 `version.json` 但程序已经在运行，需要重启程序或调用 `clear_cache()` 函数清除缓存
- 程序会按优先级查找 `version.json` 文件：
  1. 项目根目录的 `config/version.json`
  2. 安装目录的 `/usr/share/humanaize2/config/version.json`
  3. 其他可能的位置
