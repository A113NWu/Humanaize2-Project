# Humanaize 2.2 Linux Troubleshooting Guide

**← [返回主文档](./README.md)** | [📖 文档导航](./README.md)

## Table of Contents
- [Installation Issues](#installation-issues)
- [Dependency Problems](#dependency-problems)
- [Runtime Errors](#runtime-errors)
- [Service Issues](#service-issues)
- [Performance Problems](#performance-problems)
- [Getting Help](#getting-help)

---

## Installation Issues

### "Permission denied" errors

**Symptom:** Cannot execute install scripts or write to directories.

**Solution:**
```bash
# Make scripts executable
chmod +x install.sh install_deps.sh uninstall.sh

# Run with sudo for system-wide installation
sudo ./install.sh

# Or run as root
su -c "./install.sh"
```

### "Command not found" after installation

**Symptom:** `humanaize2` command not found after installation.

**Solution:**
```bash
# Check if symlinks exist
ls -la ~/.local/bin/

# Add to PATH if needed
export PATH="$HOME/.local/bin:$PATH"

# Re-create symlinks
ln -sf /opt/humanaize2/humanaize2.sh ~/.local/bin/humanaize2
```

### Repository not found errors

**Symptom:** Git cannot clone or push to repository.

**Solution:**
```bash
# Configure git
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Check SSH keys for GitHub
ssh -T git@github.com
```

---

## Dependency Problems

### Python version mismatch

**Symptom:** "Python 3.8+ required" or import errors.

**Solution:**
```bash
# Check Python version
python3 --version

# Install Python 3.8+ if needed (Ubuntu/Debian)
sudo apt-get install python3.10 python3.10-venv python3.10-dev

# Set as default
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
```

### pip installation fails

**Symptom:** Cannot install Python packages with pip.

**Solution:**
```bash
# Upgrade pip
pip3 install --upgrade pip

# Use user installation
pip3 install --user package_name

# Or use virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### tkinter not found

**Symptom:** `ModuleNotFoundError: No module named 'tkinter'`

**Solution (Ubuntu/Debian):**
```bash
sudo apt-get install python3-tk tk-dev
```

**Solution (CentOS/RHEL):**
```bash
sudo yum install python3-tkinter
```

**Solution (Arch):**
```bash
sudo pacman -S tk
```

### OpenCV not working

**Symptom:** `cv2` import errors or camera not detected.

**Solution:**
```bash
# Reinstall opencv
pip3 uninstall opencv-python
pip3 install opencv-python-headless

# For camera support
sudo apt-get install libopencv-dev python3-opencv
```

### CUDA/GPU acceleration not working

**Symptom:** CUDA errors or slow performance.

**Solution:**
```bash
# Check NVIDIA driver
nvidia-smi

# Check CUDA version
nvcc --version

# Install PyTorch with CUDA support
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

---

## Runtime Errors

### "No module named 'humanaize2'"

**Symptom:** Import errors when running.

**Solution:**
```bash
# Reinstall in development mode
cd /opt/humanaize2
pip3 install -e .

# Or add to PYTHONPATH
export PYTHONPATH="/opt/humanaize2:$PYTHONPATH"
```

### "Model file not found"

**Symptom:** LLM server fails to start.

**Solution:**
```bash
# Check model location
ls -la ~/.local/share/Humanaize2/models/
ls -la /opt/humanaize2/models/

# Download model if missing
mkdir -p ~/.local/share/Humanaize2/models/
# Place your tinyllama.gguf in this directory
```

### GUI not displaying

**Symptom:** Application starts but no window appears.

**Solution:**
```bash
# Check DISPLAY variable
echo $DISPLAY

# Set DISPLAY if needed
export DISPLAY=:0

# Install X11 utilities
sudo apt-get install x11-utils

# For WSL2, use XLaunch and set DISPLAY
export DISPLAY=$(grep -oP '(?<=nameserver ).+' /etc/resolv.conf):0
```

### Port 8080 already in use

**Symptom:** "Address already in use" error.

**Solution:**
```bash
# Find what's using port 8080
sudo lsof -i :8080
sudo netstat -tlnp | grep 8080

# Kill the process
sudo kill -9 <PID>

# Or use a different port
export HUMANIZE2_PORT=8081
```

---

## Service Issues

### Service fails to start

**Symptom:** `systemctl start humanaize2` fails.

**Solution:**
```bash
# Check service status
sudo systemctl status humanaize2

# View detailed logs
sudo journalctl -u humanaize2 -xe

# Check user configuration
cat /etc/systemd/system/humanaize2.service
```

### Service starts but immediately stops

**Symptom:** Service enters failed state.

**Solution:**
```bash
# Check for configuration errors
sudo -u humanaize humaize2

# Verify paths in service file
grep ExecStart /etc/systemd/system/humanaize2.service

# Check log files
cat ~/.local/log/humanaize2/humanaize2.log
```

### Permission denied errors with service

**Symptom:** Service cannot access files or directories.

**Solution:**
```bash
# Fix ownership
sudo chown -R humanaize:humanaize /opt/humanaize2
sudo chown -R humanaize:humanaize ~/.config/Humanaize2
sudo chown -R humanaize:humanaize ~/.local/share/Humanaize2

# Fix permissions
sudo chmod -R 755 /opt/humanaize2
sudo chmod -R 700 ~/.config/Humanaize2
```

---

## Performance Problems

### High CPU usage

**Symptom:** System becomes sluggish.

**Solution:**
```bash
# Limit CPU usage via systemd
sudo systemctl edit humanaize2

# Add:
[Service]
CPUQuota=50%
```

### Out of memory errors

**Symptom:** OOM killer terminates process.

**Solution:**
```bash
# Increase memory limit
sudo systemctl edit humanaize2

# Add:
[Service]
MemoryMax=4G
```

### Slow response time

**Symptom:** AI responses are very slow.

**Solution:**
```bash
# Enable GPU acceleration
export CUDA_VISIBLE_DEVICES=0

# Reduce context size in settings
# Or use a smaller model

# Check disk I/O
iostat -x 1
```

---

## Getting Help

### Collect Debug Information

```bash
# System info
uname -a
cat /etc/os-release

# Python environment
python3 --version
pip3 list

# Logs
journalctl -u humanaize2 --since "1 hour ago" > debug.log

# Configuration
ls -la ~/.config/Humanaize2/
cat ~/.config/Humanaize2/settings.json
```

### Report an Issue

When reporting issues, include:
1. Output of `uname -a`
2. Distribution and version
3. Python version: `python3 --version`
4. Installation method used
5. Relevant log output
6. Steps to reproduce

### Common Quick Fixes

```bash
# Clear cache
rm -rf ~/.cache/humanaize2/

# Reset configuration
rm -rf ~/.config/Humanaize2/
mkdir -p ~/.config/Humanaize2

# Reinstall dependencies
pip3 install --force-reinstall -r requirements.txt

# Full service restart
sudo systemctl daemon-reload
sudo systemctl restart humanaize2
```
