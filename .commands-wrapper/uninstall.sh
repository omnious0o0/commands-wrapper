#!/usr/bin/env bash
set -e

GREEN="\033[38;5;108m"
RED="\033[38;5;131m"
GRAY="\033[38;5;244m"
BLUE="\033[38;5;67m"
RESET="\033[0m"

printf "${BLUE}Uninstalling commands-wrapper${RESET}\n"

run_pip() {
    python3 -m pip "$@" --break-system-packages && return 0
    python3 -m pip "$@"
}

scripts_dir_from_python() {
    python3 -c "import os, site, sys, sysconfig; in_venv = getattr(sys, 'base_prefix', sys.prefix) != sys.prefix; scripts = None
if in_venv:
    scripts = sysconfig.get_path('scripts')
else:
    scheme = f'{os.name}_user'
    if scheme in sysconfig.get_scheme_names():
        scripts = sysconfig.get_path('scripts', scheme=scheme)
scripts = scripts or os.path.join(site.USER_BASE or os.path.expanduser('~'), 'bin')
print(os.path.abspath(scripts))"
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
BIN_DIR=$(scripts_dir_from_python)
BIN_PATH="$BIN_DIR/commands-wrapper"
if [ -f "$BIN_PATH" ]; then
    if ! "$BIN_PATH" sync --uninstall &>/dev/null; then
        echo -e "${GRAY}wrapper cleanup failed; continuing package uninstall.${RESET}"
    fi
fi

if ! run_pip uninstall commands-wrapper -y &>/dev/null; then
    echo -e "${RED}failed to uninstall commands-wrapper.${RESET}"
    exit 1
fi

echo -e "${GREEN}OK${RESET}"

echo -e "${GREEN}commands-wrapper uninstalled.${RESET}"
