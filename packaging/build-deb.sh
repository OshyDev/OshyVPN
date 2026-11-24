#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_VERSION="$(PYTHONPATH="$ROOT" python3 -c 'from oshy_service.version import VERSION; print(VERSION)')"
case "$APP_VERSION" in
  0.01-BETA) VERSION="0.0.1~beta" ;;
  *) echo "Add a Debian version mapping for $APP_VERSION in packaging/build-deb.sh" >&2; exit 1 ;;
esac
ARCH="${DEB_ARCH:-amd64}"
STAGE="$ROOT/build/deb-root"
rm -rf "$STAGE"
install -D -m 0755 "$ROOT/dist/oshyVPN" "$STAGE/usr/bin/oshyvpn"
install -D -m 0644 "$ROOT/README.md" "$STAGE/usr/share/doc/oshyvpn/README.md"
mkdir -p "$STAGE/DEBIAN"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: oshyvpn
Version: $VERSION
Section: net
Priority: optional
Architecture: $ARCH
Maintainer: OshyDev
Description: OshyVPN API service (beta)
 Self-contained OshyVPN API service by OshyDev.
EOF
dpkg-deb --root-owner-group --build "$STAGE" "$ROOT/dist/oshyvpn_${VERSION}_${ARCH}.deb"
