#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="${OSHYVPN_REPOSITORY:-OshyDev/oshyVPN}"
VERSION="0.0.1~beta"
ARCH="$(dpkg --print-architecture)"
ASSET="oshyvpn_${VERSION}_${ARCH}.deb"
URL="https://github.com/${REPOSITORY}/releases/latest/download/${ASSET}"
PACKAGE="$(mktemp --suffix=.deb)"
trap 'rm -f "$PACKAGE"' EXIT

curl --fail --location --silent --show-error "$URL" --output "$PACKAGE"
sudo apt install --yes "$PACKAGE"
echo "Installed OshyVPN. Start it with: oshyvpn"
