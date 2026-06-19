# Humanaize 2.2 Windows 打包指南

**← [返回主文档](./README.md)** | [📖 文档导航](./README.md)

## 快速开始

在 **Windows 10/11** 系统上按以下步骤打包：

### 1. 安装依赖软件

| 软件 | 下载地址 | 说明 |
|------|----------|------|
| Python 3.11 | https://www.python.org/downloads/windows/ | 推荐 3.11.x 版本 |
| Git | https://git-scm.com/download/win | 用于克隆项目 |
| Inno Setup 6 | https://jrsoftware.org/isdl.php | 用于创建安装程序 |

### 2. 克隆项目

打开 **命令提示符** 或 **PowerShell**：

```cmd
git clone https://github.com/your-repo/humanaize2.git
cd humanaize2
```

### 3. 创建虚拟环境（推荐）

```cmd
python -m venv venv
venv\Scripts\activate
```

### 4. 安装 Python 依赖

```cmd
pip install customtkinter requests nltk transformers torch pillow pyinstaller
```

### 5. 运行打包脚本

```cmd
cd installer\windows
build_all.bat
```

### 6. 输出文件

打包完成后，安装包位于：
- `installer_output\Humanaize2-Setup-x86_64.exe` (64位)
- `installer_output\Humanaize2-Setup-arm64.exe` (ARM64)

## 手动打包步骤

如果自动脚本有问题，可以手动执行：

### 步骤 1: 构建可执行文件

```cmd
cd ..\..
python installer\windows\build_exe.py all
```

### 步骤 2: 创建安装程序

1. 打开 Inno Setup
2. 打开 `installer\windows\humanaize2-x86_64.iss`
3. 点击 **Build > Compile**
4. 重复上述步骤处理 `humanaize2-arm64.iss`

## 常见问题

### Q: PyInstaller 报错 ModuleNotFoundError
**A:** 安装缺失的模块：
```cmd
pip install <缺失的模块名>
```

### Q: Inno Setup 编译失败
**A:** 确保已安装最新版本的 Inno Setup，并以管理员身份运行。

### Q: 杀毒软件误报
**A:** 这是正常现象，首次运行时添加信任即可。

## 注意事项

1. **模型文件**: 确保 `models` 目录中有 GGUF 格式的模型文件
2. **管理员权限**: 安装程序需要管理员权限运行
3. **Windows SDK**: 如果遇到编译错误，安装 [Windows SDK](https://developer.microsoft.com/zh-cn/windows/downloads/windows-sdk/)

## 技术说明

### 打包工具
- **PyInstaller**: 将 Python 代码打包为独立可执行文件
- **Inno Setup**: 创建 Windows 安装程序

### 架构支持
- x86_64: 主流 64 位 Windows
- ARM64: Windows on ARM（如 Surface Pro X）

### 文件结构
```
Humanaize2/
├── src/              # 源代码
├── skills/           # 技能模块
├── config/           # 配置文件
├── models/           # AI 模型（需单独放置）
└── installer/
    └── windows/      # Windows 打包脚本
```

---

*提示：由于跨平台编译的复杂性，建议在 Windows 系统上完成打包。如果需要 Linux 版本，可以使用项目中的 `build_all.sh` 脚本。*
