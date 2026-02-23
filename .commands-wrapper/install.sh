#!/usr/bin/env bash
set -e

GREEN="\033[38;5;108m"
RED="\033[38;5;131m"
BLUE="\033[38;5;67m"
GRAY="\033[38;5;244m"
RESET="\033[0m"

printf "${BLUE}Installing commands-wrapper${RESET}\n"

run_pip() {
    python3 -m pip "$@" --break-system-packages && return 0
    python3 -m pip "$@"
}

# Dependencies
echo -n -e "${GRAY}[1/4] Checking dependencies... ${RESET}"
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}python3 not found.${RESET}"
    exit 1
fi
if ! python3 -m pip --version &>/dev/null; then
    echo -e "${RED}pip not found.${RESET}"
    exit 1
fi
echo -e "${GREEN}OK${RESET}"

INSTALL_CWD=$(pwd)

# Source
echo -n -e "${GRAY}[2/4] Preparing source... ${RESET}"
TMP_DIR=""
if [ ! -f "pyproject.toml" ]; then
    if ! command -v curl &>/dev/null; then
        echo -e "${RED}curl not found (required for remote install).${RESET}"
        exit 1
    fi
    if ! command -v tar &>/dev/null; then
        echo -e "${RED}tar not found (required for remote install).${RESET}"
        exit 1
    fi
    if ! command -v mktemp &>/dev/null; then
        echo -e "${RED}mktemp not found (required for remote install).${RESET}"
        exit 1
    fi

    TMP_DIR=$(mktemp -d)
    trap 'rm -rf "$TMP_DIR"' EXIT
    curl -sSL https://github.com/omnious0o0/commands-wrapper/archive/refs/heads/main.tar.gz \
        | tar xz --strip-components=1 -C "$TMP_DIR"
    cd "$TMP_DIR"
fi
echo -e "${GREEN}OK${RESET}"

# Install
echo -n -e "${GRAY}[3/4] Installing package... ${RESET}"
run_pip uninstall commands-wrapper -y &>/dev/null || true
run_pip install . -q
echo -e "${GREEN}OK${RESET}"

# Configure
echo -n -e "${GRAY}[4/4] Configuring defaults... ${RESET}"

if [ ! -f "$INSTALL_CWD/commands.yaml" ] && [ ! -f "$INSTALL_CWD/commands.yml" ]; then
    cat <<'EOF' > "$INSTALL_CWD/commands.yaml"
# command-name:
#   description: "What this command does"
#   steps 60:                          # 60 = timeout in seconds (optional)
#     - command: "shell command here"
#     - send: "text to type into process"
#     - press_key: "enter"
#     - wait: "2"
EOF
fi

BIN_PATH=$(python3 -c "import site, os; print(os.path.join(site.USER_BASE, 'bin', 'commands-wrapper'))")
if [ -f "$BIN_PATH" ]; then
    chmod +x "$BIN_PATH"
    "$BIN_PATH" sync &>/dev/null || true
fi
echo -e "${GREEN}OK${RESET}"

# PATH check
BIN_DIR=$(python3 -c "import site, os; print(os.path.join(site.USER_BASE, 'bin'))")
if ! python3 - "$BIN_DIR" <<'PY'
import os
import sys

target = os.path.realpath(os.path.expanduser(sys.argv[1]))
path_entries = [
    os.path.realpath(os.path.expanduser(entry))
    for entry in os.environ.get("PATH", "").split(os.pathsep)
    if entry
]

sys.exit(0 if target in set(path_entries) else 1)
PY
then
    echo
    echo -e "${RED}$BIN_DIR is not in PATH.${RESET}"
    echo -e "${GRAY}Add this to your shell config and restart your shell:${RESET}"
    echo -e "export PATH=\"\$PATH:$BIN_DIR\""
fi

echo
echo -e "${GREEN}commands-wrapper installed.${RESET}"
echo -e "${GRAY}Run 'commands-wrapper --help' to get started.${RESET}"
