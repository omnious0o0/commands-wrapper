#!/usr/bin/env bash
set -e

GREEN="\033[38;5;108m"
RED="\033[38;5;131m"
BLUE="\033[38;5;67m"
GRAY="\033[38;5;244m"
RESET="\033[0m"

printf "${BLUE}Installing commands-wrapper${RESET}\n"

SOURCE_URL="${COMMANDS_WRAPPER_SOURCE_URL:-https://github.com/omnious0o0/commands-wrapper/archive/refs/heads/main.tar.gz}"
SOURCE_SHA256="${COMMANDS_WRAPPER_SOURCE_SHA256:-}"

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

file_sha256() {
    python3 - "$1" <<'PY'
import hashlib
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
digest = hashlib.sha256()
with path.open('rb') as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b''):
        digest.update(chunk)
print(digest.hexdigest())
PY
}

is_commands_wrapper_source_root() {
    local root="$1"
    [ -f "$root/pyproject.toml" ] || return 1
    [ -f "$root/.commands-wrapper/commands-wrapper" ] || return 1
    return 0
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
SCRIPT_PATH="${BASH_SOURCE[0]}"
case "$SCRIPT_PATH" in
    */*)
        SCRIPT_DIR="$(cd -- "${SCRIPT_PATH%/*}" && pwd)"
        ;;
    *)
        SCRIPT_DIR="$INSTALL_CWD"
        ;;
esac
SCRIPT_REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

# Source
echo -n -e "${GRAY}[2/4] Preparing source... ${RESET}"
TMP_DIR=""
LOCAL_SOURCE_ROOT=""
if is_commands_wrapper_source_root "$SCRIPT_REPO_ROOT"; then
    LOCAL_SOURCE_ROOT="$SCRIPT_REPO_ROOT"
elif is_commands_wrapper_source_root "$INSTALL_CWD"; then
    LOCAL_SOURCE_ROOT="$INSTALL_CWD"
fi

if [ -n "$LOCAL_SOURCE_ROOT" ]; then
    cd "$LOCAL_SOURCE_ROOT"
else
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
    ARCHIVE_PATH="$TMP_DIR/commands-wrapper.tar.gz"
    curl -fsSL "$SOURCE_URL" -o "$ARCHIVE_PATH"

    if [ -n "$SOURCE_SHA256" ]; then
        EXPECTED_SHA256=$(printf "%s" "$SOURCE_SHA256" | tr '[:upper:]' '[:lower:]')
        if ! printf "%s" "$EXPECTED_SHA256" | grep -Eq '^[0-9a-f]{64}$'; then
            echo -e "${RED}invalid COMMANDS_WRAPPER_SOURCE_SHA256 value.${RESET}"
            exit 1
        fi

        ACTUAL_SHA256=$(file_sha256 "$ARCHIVE_PATH")
        if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
            echo -e "${RED}source archive checksum mismatch.${RESET}"
            exit 1
        fi
    fi

    tar xzf "$ARCHIVE_PATH" --strip-components=1 -C "$TMP_DIR"
    cd "$TMP_DIR"
fi
echo -e "${GREEN}OK${RESET}"

# Install
echo -n -e "${GRAY}[3/4] Installing package... ${RESET}"
run_pip install --upgrade . -q
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

BIN_DIR=$(scripts_dir_from_python)
BIN_PATH="$BIN_DIR/commands-wrapper"
if [ -f "$BIN_PATH" ]; then
    chmod +x "$BIN_PATH"
    if ! "$BIN_PATH" sync &>/dev/null; then
        echo -e "${RED}wrapper sync failed.${RESET}"
        exit 1
    fi
fi
echo -e "${GREEN}OK${RESET}"

# PATH check
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
