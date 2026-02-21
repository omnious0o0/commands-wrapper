#!/usr/bin/env bash
set -e
pip uninstall commands-wrapper --break-system-packages -y > /dev/null 2>&1 || true
printf "[✓] Removal complete.\n"
