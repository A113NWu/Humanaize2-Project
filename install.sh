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

check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_warn "Running as root. Some features may require a regular user."
    fi
}

detect_distro() {
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        DISTRO=$ID
        VERSION=$VERSION_ID
    elif [[ -f /etc/centos-release ]]; then
        DISTRO="centos"
        VERSION=$(cat /etc/centos-release | grep -oE '[0-9]+\.[0-9]+' | head -1)
    else
        DISTRO="unknown"
        VERSION="unknown"
    fi

    log_info "Detected distribution: $DISTRO $VERSION"
}

check_dependencies() {
    log_info "Checking dependencies..."

    local missing_deps=()

    command -v python3 >/dev/null 2>&1 || missing_deps+=("python3")
    command -v git >/dev/null 2>&1 || missing_deps+=("git")
    command -v pip3 >/dev/null 2>&1 || missing_deps+=("python3-pip")

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_warn "Missing dependencies: ${missing_deps[*]}"
        log_info "Please run: sudo ./install_deps.sh"
        exit 1
    fi

    log_info "All dependencies are installed."
}

create_directories() {
    log_info "Creating directory structure..."

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$HOME/.local/bin"
    mkdir -p "$HOME/.local/share/applications"

    log_info "Directories created successfully."
}

install_application() {
    log_info "Installing Humanaize 2.1..."

    if [[ ! -d "$(dirname "$0")" ]]; then
        log_error "Cannot find installation files. Please run this script from the Humanaize directory."
        exit 1
    fi

    rsync -av --exclude='.git' --exclude='llama' --exclude='models' --exclude='*.gguf' --exclude='__pycache__' "$(dirname "$0")/" "$INSTALL_DIR/" 2>/dev/null || cp -r "$(dirname "$0")/"* "$INSTALL_DIR/"

    if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
        log_info "Installing Python dependencies..."
        pip3 install --user -r "$INSTALL_DIR/requirements.txt" --quiet
    fi

    chmod +x "$INSTALL_DIR/humanaize2.sh"
    chmod +x "$INSTALL_DIR/Server.sh"

    ln -sf "$INSTALL_DIR/humanaize2.sh" "$HOME/.local/bin/humanaize2"
    ln -sf "$INSTALL_DIR/Server.sh" "$HOME/.local/bin/humanaize2-server"

    log_info "Application installed successfully to $INSTALL_DIR"
}

create_systemd_service() {
    log_info "Creating systemd service..."

    if [[ $EUID -ne 0 ]]; then
        log_warn "Not running as root. Skipping systemd service installation."
        log_warn "To install systemd service, run: sudo ./install.sh --with-service"
        return
    fi

    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=Humanaize 2.1 AI Assistant
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$HOME/.local/bin/humanaize2
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment=HOME=$HOME
Environment=DISPLAY=:0

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}.service"

    log_info "Systemd service installed. Use 'sudo systemctl start ${SERVICE_NAME}' to start."
}

create_Desktop_entry() {
    log_info "Creating desktop entry..."

    cat > "$HOME/.local/share/applications/humanaize2.desktop" << EOF
[Desktop Entry]
Name=Humanaize 2.1
Comment=AI Assistant with GAN Thinking
Exec=$HOME/.local/bin/humanaize2
Icon=$INSTALL_DIR/icon.png
Terminal=false
Type=Application
Categories=Utility;AI;
Keywords=AI;assistant;GAN;chatbot;
StartupNotify=true
EOF

    chmod +x "$HOME/.local/share/applications/humanaize2.desktop"
    update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true

    log_info "Desktop entry created."
}

setup_rsyslog() {
    log_info "Setting up logging..."

    if [[ $EUID -ne 0 ]]; then
        log_warn "Not running as root. Skipping rsyslog configuration."
        return
    fi

    cat > "/etc/rsyslog.d/humanaize2.conf" << EOF
if \$programname == 'humanaize2' then {
    action(type="omfile" dynaFile="HUMANIZE2" file="/dev/null")
    stop
}
EOF

    cat > "/etc/logrotate.d/humanaize2" << EOF
$LOG_DIR/humanaize2.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 $USER $USER
}
EOF

    systemctl restart rsyslog 2>/dev/null || true

    log_info "Logging configured."
}

print_success() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Humanaize 2.1 Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Installation directory: $INSTALL_DIR"
    echo "Configuration: $CONFIG_DIR"
    echo "Data directory: $DATA_DIR"
    echo "Log directory: $LOG_DIR"
    echo ""
    echo "To start Humanaize 2.1:"
    echo "  $HOME/.local/bin/humanaize2"
    echo ""
    if [[ $EUID -eq 0 ]]; then
        echo "To start as service:"
        echo "  sudo systemctl start ${SERVICE_NAME}"
        echo ""
    fi
    echo "For GUI mode, run: humaize2"
    echo "For server mode, run: humaize2-server"
    echo ""
}

main() {
    log_info "Starting Humanaize 2.1 installation..."
    echo ""

    check_root
    detect_distro
    check_dependencies
    create_directories
    install_application

    if [[ "$1" == "--with-service" ]] || [[ "$1" == "-s" ]]; then
        create_systemd_service
    fi

    create_Desktop_entry
    setup_rsyslog
    print_success
}

main "$@"