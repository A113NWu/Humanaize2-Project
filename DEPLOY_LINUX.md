# Humanaize 2.1 Linux Deployment Guide

## Table of Contents
- [Supported Distributions](#supported-distributions)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Post-Installation](#post-installation)
- [Systemd Service](#systemd-service)
- [Uninstallation](#uninstallation)
- [Configuration](#configuration)

---

## Supported Distributions

| Distribution | Version | Status |
|--------------|---------|--------|
| Ubuntu | 20.04 LTS | Tested |
| Ubuntu | 22.04 LTS | Tested |
| Debian | 11 (Bullseye) | Tested |
| CentOS | 7 | Tested |
| CentOS | 8 | Tested |
| Fedora | 35+ | Compatible |
| Rocky Linux | 8+ | Compatible |
| Arch Linux | Rolling | Compatible |

---

## Prerequisites

### System Requirements
- **CPU**: x86_64 or ARM64
- **Memory**: 4GB minimum (8GB recommended)
- **Disk Space**: 2GB for application + model files
- **Python**: 3.8 or higher

### Required Packages
```bash
sudo apt-get install python3 python3-pip git curl wget build-essential
```

---

## Installation

### Step 1: Install System Dependencies

For Ubuntu/Debian:
```bash
chmod +x install_deps.sh
sudo ./install_deps.sh
```

For CentOS/RHEL:
```bash
chmod +x install_deps.sh
sudo ./install_deps.sh
```

### Step 2: Install Humanaize 2.1

```bash
chmod +x install.sh
sudo ./install.sh
```

For installation with systemd service:
```bash
sudo ./install.sh --with-service
```

### Step 3: Verify Installation

```bash
humanaize2 --version
```

---

## Post-Installation

### Starting the Application

**GUI Mode (Default):**
```bash
humanaize2
```

**Server Mode (No GUI):**
```bash
humanaize2-server
```

**CLI Mode:**
```bash
humanaize2 boot
```

### Model File Location

Place your model file at:
```
$HOME/.local/share/Humanaize2/models/tinyllama.gguf
```

Or in the installation directory:
```
/opt/humanaize2/models/tinyllama.gguf
```

---

## Systemd Service

### Install as System Service

```bash
sudo ./install.sh --with-service
```

### Service Commands

**Start the service:**
```bash
sudo systemctl start humanaize2
```

**Stop the service:**
```bash
sudo systemctl stop humanaize2
```

**Restart the service:**
```bash
sudo systemctl restart humanaize2
```

**Check status:**
```bash
sudo systemctl status humanaize2
```

**Enable on boot:**
```bash
sudo systemctl enable humanaize2
```

### Viewing Logs

**Systemd journal:**
```bash
sudo journalctl -u humanaize2 -f
```

**Application log:**
```bash
tail -f ~/.local/log/humanaize2/humanaize2.log
```

---

## Uninstallation

```bash
chmod +x uninstall.sh
sudo ./uninstall.sh
```

---

## Configuration

### Directories

| Purpose | Path |
|---------|------|
| Configuration | `~/.config/Humanaize2/` |
| Data | `~/.local/share/Humanaize2/` |
| Logs | `~/.local/log/humanaize2/` |
| Cache | `~/.cache/humanaize2/` |

### Environment Variables

You can customize behavior with environment variables:

```bash
export HUMANIZE2_CONFIG_DIR="$HOME/.config/Humanaize2"
export HUMANIZE2_DATA_DIR="$HOME/.local/share/Humanaize2"
export HUMANIZE2_LOG_DIR="$HOME/.local/log/humanaize2"
export HUMANIZE2_MODEL_PATH="$HOME/.local/share/Humanaize2/models/tinyllama.gguf"
```

---

## Firewall Configuration

If using remote access, allow the LLM server port:

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow 8080/tcp

# Firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

---

## Troubleshooting

For common issues and solutions, see [TROUBLESHOOTING_LINUX.md](TROUBLESHOOTING_LINUX.md)

### Quick Diagnostics

```bash
# Check Python version
python3 --version

# Check dependencies
python3 -c "import tkinter; import cv2; import requests; print('All dependencies OK')"

# Check LLM server
curl http://127.0.0.1:8080

# View system logs
sudo journalctl -u humanaize2 -n 50
```

---

## Performance Tuning

### GPU Acceleration

For NVIDIA GPUs with CUDA:
```bash
export CUDA_VISIBLE_DEVICES=0
humanaize2
```

### Memory Limits

Edit the systemd service to adjust memory limits:
```bash
sudo nano /etc/systemd/system/humanaize2.service
```

Modify the `MemoryMax` value:
```
MemoryMax=4G
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart humanaize2
```
