#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="${OSHYVPN_REPOSITORY:-OshyDev/oshyVPN}"
ARCH="$(dpkg --print-architecture)"
ASSET="oshyvpn_${ARCH}.deb"
URL="https://github.com/${REPOSITORY}/releases/latest/download/${ASSET}"
PACKAGE="$(mktemp --suffix=.deb)"
trap 'rm -f "$PACKAGE"' EXIT

if ! curl --fail --location --silent --show-error "$URL" --output "$PACKAGE"; then
  echo "OshyVPN package not found: $URL" >&2
  echo "No published release asset is available yet. Check https://github.com/${REPOSITORY}/releases" >&2
  exit 1
fi
sudo apt install --yes "$PACKAGE"
echo "Installed OshyVPN. Start it with: oshyvpn"
