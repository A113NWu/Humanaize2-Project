#!/bin/bash

set -e

INSTALL_DIR="/opt/humanaize2"
USER_NAME="humanaize"
SERVICE_NAME="humanaize2"
CONFIG_DIR="$HOME/.config/Humanaize2"
DATA_DIR="$HOME/.local/share/Humanaize2"
LOG_DIR="$HOME/.local/log"

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

confirm() {
    read -p "$1 [y/N]: " response
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

stop_service() {
    if systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
        log_info "Stopping ${SERVICE_NAME} service..."
        sudo systemctl stop "${SERVICE_NAME}.service"
        sudo systemctl disable "${SERVICE_NAME}.service" 2>/dev/null || true
    fi
}

remove_systemd_service() {
    if [[ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]]; then
        log_info "Removing systemd service..."
        sudo rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
        sudo systemctl daemon-reload
    fi
}

remove_rsyslog_config() {
    log_info "Removing rsyslog configuration..."
    sudo rm -f /etc/rsyslog.d/humanaize2.conf 2>/dev/null || true
    sudo rm -f /etc/logrotate.d/humanaize2 2>/dev/null || true
}

remove_symlinks() {
    log_info "Removing symlinks..."

    rm -f "$HOME/.local/bin/humanaize2"
    rm -f "$HOME/.local/bin/humanaize2-server"
    rm -f "$HOME/.local/share/applications/humanaize2.desktop"
}

remove_directories() {
    log_info "Removing directories..."

    if [[ -d "$INSTALL_DIR" ]]; then
        if confirm "Remove installation directory ($INSTALL_DIR)?"; then
            sudo rm -rf "$INSTALL_DIR"
            log_info "Removed $INSTALL_DIR"
        fi
    fi

    if confirm "Remove configuration directory ($CONFIG_DIR)?"; then
        rm -rf "$CONFIG_DIR"
        log_info "Removed $CONFIG_DIR"
    fi

    if confirm "Remove data directory ($DATA_DIR)?"; then
        rm -rf "$DATA_DIR"
        log_info "Removed $DATA_DIR"
    fi

    if confirm "Remove log directory ($LOG_DIR)?"; then
        rm -rf "$LOG_DIR"
        log_info "Removed $LOG_DIR"
    fi
}

remove_python_packages() {
    if confirm "Remove Python packages installed by Humanaize?"; then
        log_info "Removing Python packages..."
        pip3 uninstall -y humanaize2 2>/dev/null || true
    fi
}

print_complete() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Humanaize 2.1 Uninstallation Complete${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Humanaize 2.1 has been removed from your system."
    echo ""
    echo "Note: Your models directory and personal data may still exist."
    echo "      Manually remove if needed:"
    echo "        - ~/.config/Humanaize2/"
    echo "        - ~/.local/share/Humanaize2/"
    echo "        - ~/.local/log/humanaize2/"
    echo ""
}

main() {
    log_info "Starting Humanaize 2.1 uninstallation..."
    echo ""

    if [[ $EUID -eq 0 ]]; then
        log_warn "Running as root. Some operations may be skipped."
    fi

    if ! confirm "Are you sure you want to uninstall Humanaize 2.1?"; then
        log_info "Uninstallation cancelled."
        exit 0
    fi

    echo ""
    log_info "Step 1: Stopping service..."
    stop_service

    log_info "Step 2: Removing systemd service..."
    remove_systemd_service

    log_info "Step 3: Removing logging configuration..."
    remove_rsyslog_config

    log_info "Step 4: Removing symlinks and shortcuts..."
    remove_symlinks

    log_info "Step 5: Removing directories..."
    remove_directories

    log_info "Step 6: Cleaning up Python packages..."
    remove_python_packages

    print_complete
}

main "$@"