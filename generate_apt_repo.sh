#!/bin/bash
# -*- coding: utf-8 -*-
"""
Humanaize 2.0 APT Repository Generator
生成 APT 仓库索引文件
"""

set -e

REPO_DIR="apt-repo"
DIST_NAME="stable"
COMPONENT="main"
ARCHS=("amd64" "arm64" "all")

echo "=============================================="
echo "Humanaize 2.0 APT Repository Generator"
echo "=============================================="

# 创建目录
mkdir -p ${REPO_DIR}/dists/${DIST_NAME}/${COMPONENT}/binary-{amd64,arm64,all}

# 生成 Packages 文件
for arch in "${ARCHS[@]}"; do
    echo "生成 ${arch} 架构的 Packages 文件..."
    ARCH_DIR="${REPO_DIR}/dists/${DIST_NAME}/${COMPONENT}/binary-${arch}"
    
    # 使用 dpkg-scanpackages 生成索引
    if command -v dpkg-scanpackages &> /dev/null; then
        dpkg-scanpackages ${ARCH_DIR} /dev/null | gzip -9 > ${ARCH_DIR}/Packages.gz
    else
        # 如果没有 dpkg-scanpackages，手动生成
        echo "警告: dpkg-scanpackages 不可用，跳过生成"
    fi
done

# 生成 Release 文件
echo "生成 Release 文件..."
cd ${REPO_DIR}
cat > dists/${DIST_NAME}/Release << EOF
Origin: Humanaize2
Label: Humanaize2 Repository
Suite: ${DIST_NAME}
Version: 2.2.0
Codename: ${DIST_NAME}
Date: $(date -R)
Architectures: amd64 arm64 all
Components: ${COMPONENT}
Description: Humanaize 2.0 AI Assistant Repository
EOF

# 生成 InRelease 文件（包含 SHA256 校验）
echo "生成校验文件..."
if command -v apt-ftparchive &> /dev/null; then
    apt-ftparchive release dists/${DIST_NAME} > dists/${DIST_NAME}/InRelease
    
    # 更新 Release 文件的 SHA256
    apt-ftparchive release dists/${DIST_NAME} >> dists/${DIST_NAME}/Release
fi

echo ""
echo "=============================================="
echo "APT 仓库生成完成!"
echo "=============================================="
echo ""
echo "仓库结构:"
echo "  apt-repo/"
echo "  ├── dists/"
echo "  │   └── stable/"
echo "  │       ├── Release"
echo "  │       ├── InRelease"
echo "  │       └── main/"
echo "  │           ├── binary-amd64/"
echo "  │           │   ├── humanaize2_2.2.0_amd64.deb"
echo "  │           │   └── Packages.gz"
echo "  │           ├── binary-arm64/"
echo "  │           │   ├── humanaize2_2.2.0_arm64.deb"
echo "  │           │   └── Packages.gz"
echo "  │           └── binary-all/"
echo "  │               ├── humanaize2_2.2.0_all.deb"
echo "  │               └── Packages.gz"
echo ""
echo "下一步:"
echo "  1. 将 apt-repo/ 目录部署到 Web 服务器"
echo "  2. 用户通过以下命令安装:"
echo ""
echo "     echo 'deb https://your-domain.com/apt-repo stable main' | sudo tee /etc/apt/sources.list.d/humanaize2.list"
echo "     sudo apt update"
echo "     sudo apt install humanaize2"
echo ""
echo "=============================================="
