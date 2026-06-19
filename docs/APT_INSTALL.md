# Humanaize 2.0 APT 仓库安装指南

**← [返回主文档](../docs/README.md)** | [📖 文档导航](../docs/README.md)

## 快速安装

### 方法 1: 使用仓库（推荐）

```bash
# 1. 添加仓库
echo 'deb [trusted=yes] https://your-server.com/apt-repo stable main' | sudo tee /etc/apt/sources.list.d/humanaize2.list

# 2. 更新包列表
sudo apt update

# 3. 安装 Humanaize 2.0
sudo apt install humanaize2
```

### 方法 2: 直接下载安装包

```bash
# 下载安装包
wget https://your-server.com/apt-repo/humanaize2_2.2.0_amd64.deb

# 安装
sudo dpkg -i humanaize2_2.2.0_amd64.deb
```

## 安装后配置

### 运行应用

```bash
# 在 GUI 环境中运行
humanaize2

# 或在终端中运行
humanaize2-cli
```

### 卸载

```bash
# 卸载应用
sudo apt remove humanaize2

# 清除配置（可选）
sudo apt purge humanaize2
```

## 故障排除

### 问题：无法找到软件包

**解决方案**：确保已正确添加仓库并执行 `sudo apt update`

### 问题：依赖关系错误

**解决方案**：
```bash
sudo apt install -f
```

### 问题：签名验证失败

**解决方案**：安装时使用 `[trusted=yes]` 选项，或导入 GPG 密钥：
```bash
wget -qO - https://your-server.com/apt-repo/gpg.key | sudo apt-key add -
```

## 架构选择

| 架构 | 安装包 | 说明 |
|------|--------|------|
| amd64 | `humanaize2_2.2.0_amd64.deb` | 64位 x86 处理器 |
| arm64 | `humanaize2_2.2.0_arm64.deb` | 64位 ARM 处理器 |
| all | `humanaize2_2.2.0_all.deb` | 所有架构通用 |

## 自动更新

启用仓库后，可以通过以下命令更新：

```bash
sudo apt update && sudo apt upgrade humanaize2
```

## 系统要求

- Ubuntu 18.04+ / Debian 10+
- Python 3.8+
- 至少 2GB 可用磁盘空间
- 4GB+ RAM（推荐用于 AI 模型）

---

*如需帮助，请访问项目主页：https://github.com/A113NWu/Humanaize2-Project*
