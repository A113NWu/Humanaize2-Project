#!/bin/bash
# Build RPM package for Humanaize 2.0 Agent

set -e

# Configuration
PACKAGE_NAME="humanaize2"
VERSION="2.2.3"
RELEASE="1"
ARCH="noarch"
BUILD_DIR="rpmbuild"

# Clean previous build
rm -rf "$BUILD_DIR"

# Create RPM build directory structure
mkdir -p "$BUILD_DIR/SOURCES"
mkdir -p "$BUILD_DIR/SPECS"
mkdir -p "$BUILD_DIR/BUILD"
mkdir -p "$BUILD_DIR/RPMS"
mkdir -p "$BUILD_DIR/SRPMS"

# Create source archive
cd ../..
tar -czvf "$BUILD_DIR/SOURCES/$PACKAGE_NAME-$VERSION.tar.gz" \
    src/ \
    skills/ \
    version.json \
    requirements.txt \
    pyproject.toml \
    LICENSE \
    README.md \
    humanaize2.sh \
    server.sh
cd installer/linux

# Create spec file
cat > "$BUILD_DIR/SPECS/$PACKAGE_NAME.spec" << EOF
Name:           $PACKAGE_NAME
Version:        $VERSION
Release:        $RELEASE%{?dist}
Summary:        Humanaize 2.0 Agent - An AI-powered personal assistant

License:        MIT
URL:            https://github.com/A113NWu/Humanaize2-Project
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
Requires:       python3 >= 3.8
Requires:       python3-pip

%description
A sophisticated AI agent with memory, reflection, and various skills
to assist with daily tasks.

%prep
%setup -q

%build
# No build required

%install
mkdir -p %{buildroot}/usr/share/humanaize2
mkdir -p %{buildroot}/etc/systemd/system
mkdir -p %{buildroot}/var/lib/humanaize

cp -r src %{buildroot}/usr/share/humanaize2/
cp -r skills %{buildroot}/usr/share/humanaize2/
cp version.json %{buildroot}/usr/share/humanaize2/
cp requirements.txt %{buildroot}/usr/share/humanaize2/
cp pyproject.toml %{buildroot}/usr/share/humanaize2/
cp LICENSE %{buildroot}/usr/share/humanaize2/
cp README.md %{buildroot}/usr/share/humanaize2/
cp humanaize2.sh %{buildroot}/usr/share/humanaize2/
cp server.sh %{buildroot}/usr/share/humanaize2/

# Systemd service
cat > %{buildroot}/etc/systemd/system/humanaize2.service << 'SERVICE_EOF'
[Unit]
Description=Humanaize 2.0 Agent
After=network.target

[Service]
Type=simple
User=humanaize
Group=humanaize
WorkingDirectory=/usr/share/humanaize2
ExecStart=/usr/bin/python3 src/core/main.py boot
Restart=always
RestartSec=5
Environment="PYTHONPATH=/usr/share/humanaize2"

[Install]
WantedBy=multi-user.target
SERVICE_EOF

%pre
# Create system user
if ! id humanaize &>/dev/null; then
    useradd --system --home /var/lib/humanaize humanaize
fi

%post
# Install dependencies
pip3 install -r /usr/share/humanaize2/requirements.txt

# Create symlink
ln -sf /usr/share/humanaize2/humanaize2.sh /usr/local/bin/humanaize2

# Enable service
systemctl daemon-reload
systemctl enable humanaize2.service
systemctl start humanaize2.service

%preun
systemctl stop humanaize2.service

%postun
rm -f /usr/local/bin/humanaize2
systemctl disable humanaize2.service

%files
/usr/share/humanaize2/
/etc/systemd/system/humanaize2.service
/var/lib/humanaize/

%changelog
* $(date +"%a %b %d %Y") Humanaize Project <humanaize@example.com> - %{version}-%{release}
- Initial release
EOF

# Build RPM
rpmbuild --define "_topdir $BUILD_DIR" -ba "$BUILD_DIR/SPECS/$PACKAGE_NAME.spec"

# Copy packages to output directory
mkdir -p output
cp "$BUILD_DIR/RPMS/$ARCH/$PACKAGE_NAME-$VERSION-$RELEASE*.rpm" output/
cp "$BUILD_DIR/SRPMS/$PACKAGE_NAME-$VERSION-$RELEASE*.src.rpm" output/

echo "RPM package built successfully!"
echo "Packages location: output/"