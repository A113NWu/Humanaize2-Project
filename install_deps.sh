#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

detect_distro() {
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        DISTRO=$ID
        VERSION=$VERSION_ID
    elif [[ -f /etc/centos-release ]]; then
        DISTRO="centos"
        VERSION=$(cat /etc/centos-release | grep -oE '[0-9]+\.[0-9]+' | head -1)
    elif [[ -f /etc/debian_version ]]; then
        DISTRO="debian"
        VERSION=$(cat /etc/debian_version)
    else
        DISTRO="unknown"
        VERSION="unknown"
    fi

    echo "Detected: $DISTRO $VERSION"
}

install_ubuntu_debian() {
    log_info "Installing dependencies for Ubuntu/Debian..."

    sudo apt-get update

    sudo apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        git \
        curl \
        wget \
        build-essential \
        libssl-dev \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        libgl1-mesa-glx \
        libglib2.0-0 \
        ffmpeg \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgomp1 \
        portaudio19-dev \
        pkg-config \
        qt5-default \
        libqt5gui5 \
        libqt5core5a \
        libopencv-dev \
        python3-opencv

    log_info "Installing Python packages..."
    pip3 install --upgrade pip setuptools wheel

    if [[ -f requirements.txt ]]; then
        pip3 install -r requirements.txt
    fi

    log_info "Ubuntu/Debian dependencies installed successfully."
}

install_centos_rhel() {
    log_info "Installing dependencies for CentOS/RHEL..."

    if command -v dnf >/dev/null 2>&1; then
        PKG_MANAGER="dnf"
    elif command -v yum >/dev/null 2>&1; then
        PKG_MANAGER="yum"
    else
        log_error "Cannot find dnf or yum package manager"
        exit 1
    fi

    sudo $PKG_MANAGER install -y \
        python3 \
        python3-pip \
        git \
        curl \
        wget \
        gcc \
        gcc-c++ \
        make \
        openssl-devel \
        libffi-devel \
        libxml2-devel \
        libxslt-devel \
        zlib-devel \
        mesa-libGL \
        glib2 \
        ffmpeg \
        opencv-devel \
        portaudio-devel \
        qt5-qtbase \
        qt5-qtbase-gui

    log_info "Installing Python packages..."
    pip3 install --upgrade pip setuptools wheel

    if [[ -f requirements.txt ]]; then
        pip3 install -r requirements.txt
    fi

    log_info "CentOS/RHEL dependencies installed successfully."
}

install_arch() {
    log_info "Installing dependencies for Arch Linux..."

    sudo pacman -Sy --noconfirm \
        python \
        python-pip \
        git \
        curl \
        wget \
        base-devel \
        openssl \
        libffi \
        libxml2 \
        libxslt \
        zlib \
        mesa \
        glib2 \
        ffmpeg \
        opencv \
        portaudio \
        qt5-base

    log_info "Installing Python packages..."
    pip3 install --upgrade pip setuptools wheel

    if [[ -f requirements.txt ]]; then
        pip3 install -r requirements.txt
    fi

    log_info "Arch Linux dependencies installed successfully."
}

main() {
    log_info "Starting dependency installation..."
    echo ""

    if [[ $EUID -ne 0 ]]; then
        log_warn "Running as non-root. Some installations may require sudo."
    fi

    detect_distro

    case "$DISTRO" in
        ubuntu|debian|linuxmint|pop)
            install_ubuntu_debian
            ;;
        centos|rhel|fedora|rocky|alma)
            install_centos_rhel
            ;;
        arch|manjaro|endeavouros)
            install_arch
            ;;
        *)
            log_warn "Unknown distribution: $DISTRO"
            log_info "Attempting generic installation..."
            install_ubuntu_debian
            ;;
    esac

    echo ""
    log_info "========================================"
    log_info "  Dependency Installation Complete!"
    log_info "========================================"
    echo ""
    log_info "Next steps:"
    log_info "  1. Run: ./install.sh"
    log_info "  2. Configure your model path if needed"
    log_info "  3. Run: humaize2 to start the application"
    echo ""
}

main "$@"