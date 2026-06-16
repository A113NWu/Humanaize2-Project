# Humanaize 2.0 v2.2.0 發布說明

## 下載安裝

直接下載 deb 套件包進行安裝：

| 架構 | 下載連結 | 說明 |
|------|----------|------|
| amd64 | [humanaize2_2.2.0_amd64.deb](amd64/humanaize2_2.2.0_amd64.deb) | 64位元 x86 處理器 |
| arm64 | [humanaize2_2.2.0_arm64.deb](arm64/humanaize2_2.2.0_arm64.deb) | 64位元 ARM 處理器 |
| all | [humanaize2_2.2.0_all.deb](all/humanaize2_2.2.0_all.deb) | 所有架構通用 |

## 安裝方式

### 方法 1：直接安裝（推薦）

```bash
# 下載對應架構的 deb 檔案
wget https://github.com/A113NWu/Humanaize2-Project/releases/v2.2.0/humanaize2_2.2.0_amd64.deb

# 安裝
sudo dpkg -i humanaize2_2.2.0_amd64.deb

# 修復依賴關係（如有需要）
sudo apt install -f
```

### 方法 2：使用 Gdebi

```bash
sudo apt install gdebi
sudo gdebi humanaize2_2.2.0_amd64.deb
```

## 運行方式

```bash
# 在 GUI 環境中運行
humanaize2

# 或在終端中運行
humanaize2-cli
```

## 新功能

- 🧠 **AI 自我開發模組**：AI 可以自動適應用戶習慣並優化效能
- ⚡ **閒置時間自我優化**：在 GAN 閒置時分析效能指標和代碼品質
- 📐 **自適應 UI 佈局**：所有區域可隨視窗縮放自動調整大小
- 🔧 **模組化架構**：分離 Core 和 AI Selfdevelop 模組

## 系統需求

- Ubuntu 18.04+ / Debian 10+
- Python 3.8+
- 至少 2GB 可用磁碟空間
- 4GB+ RAM（推薦用於 AI 模型）

## 卸載

```bash
# 卸載應用
sudo apt remove humanaize2

# 清除配置（可選）
sudo apt purge humanaize2
```

## 問題排除

### 依賴關係錯誤

```bash
sudo apt install -f
```

### 無法找到指令

```bash
# 檢查是否正確安裝
dpkg -L humanaize2 | grep bin

# 或使用完整路徑
/usr/bin/humanaize2
```

---

完整項目原始碼：https://github.com/A113NWu/Humanaize2-Project
