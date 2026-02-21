#!/usr/bin/env bash
set -e

GREEN="\033[38;5;108m"
GRAY="\033[38;5;244m"
BLUE="\033[38;5;67m"
RESET="\033[0m"

printf "${BLUE}Uninstalling commands-wrapper${RESET}\n"

run_pip() {
    python3 -m pip "$@" --break-system-packages && return 0
    python3 -m pip "$@"
}

if ! command -v python3 &>/dev/null; then
    echo -e "${GRAY}python3 not found; nothing to uninstall.${RESET}"
    exit 0
fi

if ! python3 -m pip --version &>/dev/null; then
    echo -e "${GRAY}pip not found; nothing to uninstall.${RESET}"
    exit 0
fi

echo -n -e "${GRAY}Removing package... ${RESET}"
BIN_PATH=$(python3 -c "import site, os; print(os.path.join(site.USER_BASE, 'bin', 'commands-wrapper'))")
if [ -f "$BIN_PATH" ]; then
    "$BIN_PATH" sync --uninstall &>/dev/null || true
fi
run_pip uninstall commands-wrapper -y &>/dev/null || true
echo -e "${GREEN}OK${RESET}"

echo -e "${GREEN}commands-wrapper uninstalled.${RESET}"
