#!/bin/sh
# Install what `make firered` and `make check` need on Ubuntu/Debian: the ARM GBA toolchain, libpng and Python.
# Used by CI and as the setup script for Claude cloud environments. Safe to run more than once.
#   sh scripts/setup-toolchain.sh
set -eu
SUDO=""
[ "$(id -u)" -eq 0 ] || SUDO="sudo"
PKGS="build-essential binutils-arm-none-eabi gcc-arm-none-eabi libnewlib-arm-none-eabi libpng-dev python3 git"

missing=""
for p in $PKGS; do
  dpkg -s "$p" >/dev/null 2>&1 || missing="$missing $p"
done
if [ -n "$missing" ]; then
  $SUDO apt-get update -q
  $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $missing
fi
arm-none-eabi-gcc --version | head -1
