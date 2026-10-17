#!/data/data/com.termux/files/usr/bin/bash
# Humanaize2 - Termux (Android) 一鍵安裝腳本
# 用法：
#   pkg install git -y
#   git clone <repo_url> && cd Humanaize_2_1
#   bash install_termux.sh
# 安裝完成後啟動：
#   bash humanaize2.sh boot
# 然後用手機瀏覽器打開 http://127.0.0.1:8082/

set -e

echo "==> 更新 Termux 包索引..."
pkg update -y

echo "==> 安裝 Python 與 git..."
pkg install -y python git

echo "==> 安裝 Python 依賴（Termux 子集，見 requirements-termux.txt）..."
pip install --upgrade pip
pip install -r requirements-termux.txt

echo ""
echo "==> 安裝完成！"
echo "啟動方式：  bash humanaize2.sh boot"
echo "CLI 模式：  bash humanaize2.sh boot -m cli"
echo "然後用瀏覽器打開 http://127.0.0.1:8082/"
echo ""
echo "提示：本地 llama 模型在 Termux 上不可用，請在設置頁使用 API"
echo "（設置 → 模型，填 OpenRouter / 小米 MiMo 的接口與 Key）。"
