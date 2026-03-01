#!/usr/bin/env bash
set -euo pipefail

GREEN="\033[38;5;108m"
RED="\033[38;5;131m"
BLUE="\033[38;5;67m"
GRAY="\033[38;5;244m"
YELLOW="\033[38;5;214m"
RESET="\033[0m"

PRIMARY_WRAPPER="commands-wrapper"
SHORT_ALIAS="cw"

PATH_BLOCK_START='# >>> commands-wrapper path >>>'
PATH_BLOCK_END='# <<< commands-wrapper path <<<'

TOTAL_STEPS=9
CURRENT_STEP=0

SOURCE_URL="${COMMANDS_WRAPPER_SOURCE_URL:-https://github.com/omnious0o0/commands-wrapper/archive/refs/heads/main.tar.gz}"
SOURCE_SHA256="${COMMANDS_WRAPPER_SOURCE_SHA256:-}"

print_logo() {
    printf '%s\n' \
        '  ____ ___  __  __ __  __    _    _   _ ____  ____' \
        ' / ___/ _ \|  \/  |  \/  |  / \  | \ | |  _ \/ ___|' \
        '| |  | | | | |\/| | |\/| | / _ \ |  \| | | | \___ \' \
        '| |__| |_| | |  | | |  | |/ ___ \| |\  | |_| |___) |' \
        ' \____\___/|_|  |_|_|  |_/_/   \_\_| \_|____/|____/' \
        '' \
        '__        _______    _    ____  ____  _____ ____' \
        '\ \      / /_   _|  / \  |  _ \|  _ \| ____|  _ \' \
        ' \ \ /\ / /  | |   / _ \ | |_) | |_) |  _| | |_) |' \
        '  \ V  V /   | |  / ___ \|  __/|  __/| |___|  _ <' \
        '   \_/\_/    |_| /_/   \_\_|   |_|   |_____|_| \_\'
}

draw_progress() {
    local label="$1"
    local width=28
    local filled=$((CURRENT_STEP * width / TOTAL_STEPS))
    local empty=$((width - filled))
    local bar
    local filled_bar
    local empty_bar
    filled_bar="$(printf '%*s' "$filled" '')"
    empty_bar="$(printf '%*s' "$empty" '')"
    filled_bar="${filled_bar// /#}"
    empty_bar="${empty_bar// /-}"
    bar="${filled_bar}${empty_bar}"
    printf "${BLUE}[%s] (%d/%d)${RESET} %s\n" "$bar" "$CURRENT_STEP" "$TOTAL_STEPS" "$label"
}

start_step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    draw_progress "$1"
}

step_ok() {
    printf "${GREEN}  OK${RESET}\n"
}

step_warn() {
    printf "${YELLOW}  WARN:${RESET} %s\n" "$1"
}

die() {
    printf "${RED}ERROR:${RESET} %s\n" "$1" >&2
    exit 1
}

run_pip() {
    if python3 -m pip "$@" --break-system-packages; then
        return 0
    fi
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

user_config_dir_from_python() {
    python3 - <<'PY'
import os

if os.name == 'nt':
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    print(os.path.join(base, 'commands-wrapper'))
else:
    xdg = os.environ.get('XDG_CONFIG_HOME')
    if xdg:
        print(os.path.join(os.path.expanduser(xdg), 'commands-wrapper'))
    else:
        print(os.path.join(os.path.expanduser('~'), '.config', 'commands-wrapper'))
PY
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

path_has_dir() {
    local target="$1"
    case ":$PATH:" in
        *":$target:"*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

path_block_for_bin_dir() {
    local bin_dir="$1"
    printf '%s\n' \
        "$PATH_BLOCK_START" \
        "if [ -d \"$bin_dir\" ]; then" \
        "    case \":\$PATH:\" in" \
        "        *\":$bin_dir:\"*) ;;" \
        "        *) export PATH=\"$bin_dir:\$PATH\" ;;" \
        "    esac" \
        "fi" \
        "$PATH_BLOCK_END"
}

build_updated_path_block_content() {
    local block="$1"
    python3 - "$PATH_BLOCK_START" "$PATH_BLOCK_END" "$block" <<'PY'
import re
import sys

start, end, block = sys.argv[1], sys.argv[2], sys.argv[3]
existing = sys.stdin.read()

pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
if pattern.search(existing):
    updated = pattern.sub(block, existing, count=1)
else:
    if existing and not existing.endswith("\n"):
        updated = existing + "\n\n" + block + "\n"
    elif existing:
        updated = existing + "\n" + block + "\n"
    else:
        updated = block + "\n"

sys.stdout.write(updated)
PY
}

append_path_block() {
    local rc_path="$1"
    local block="$2"
    local existing=""

    if [ -f "$rc_path" ]; then
        if ! existing="$(<"$rc_path")"; then
            existing=""
        fi
    fi

    local parent
    parent="$(dirname "$rc_path")"
    if [ -n "$parent" ]; then
        mkdir -p "$parent" || return 1
    fi

    local updated
    if ! updated="$(printf '%s' "$existing" | build_updated_path_block_content "$block")"; then
        return 1
    fi

    if [ "$updated" = "$existing" ]; then
        return 0
    fi

    printf '%s' "$updated" > "$rc_path" || return 1
    return 0
}

ensure_path_persistence() {
    local bin_dir="$1"
    local shell_name
    shell_name="$(basename "${SHELL:-}")"
    local candidates=()

    case "$shell_name" in
        zsh)
            candidates=("$HOME/.zshrc" "$HOME/.profile")
            ;;
        bash|sh)
            candidates=("$HOME/.bashrc" "$HOME/.profile")
            ;;
        *)
            candidates=("$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile")
            ;;
    esac

    local block
    block="$(path_block_for_bin_dir "$bin_dir")"
    local rc_path

    for rc_path in "${candidates[@]}"; do
        if append_path_block "$rc_path" "$block"; then
            printf '%s\n' "$rc_path"
            return 0
        fi
    done

    return 1
}

run_sync_with_retry() {
    local wrapper_path="$1"
    local sync_log_first="${TMPDIR:-/tmp}/commands-wrapper-sync-$$.log"
    local sync_log_second="${TMPDIR:-/tmp}/commands-wrapper-sync-retry-$$.log"

    if "$wrapper_path" sync >"$sync_log_first" 2>&1; then
        rm -f "$sync_log_first" "$sync_log_second"
        return 0
    fi

    step_warn "Initial wrapper sync failed; retrying with diagnostics."
    if "$wrapper_path" sync >"$sync_log_second" 2>&1; then
        rm -f "$sync_log_first" "$sync_log_second"
        return 0
    fi

    if [ -f "$sync_log_first" ]; then
        printf "${RED}Sync attempt output:${RESET}\n" >&2
        while IFS= read -r log_line; do
            printf '%s\n' "$log_line" >&2
        done < "$sync_log_first"
    fi

    if [ -f "$sync_log_second" ]; then
        printf "${RED}Retry sync output:${RESET}\n" >&2
        while IFS= read -r log_line; do
            printf '%s\n' "$log_line" >&2
        done < "$sync_log_second"
    fi

    rm -f "$sync_log_first" "$sync_log_second"
    return 1
}

print_logo
printf "${BLUE}Installing commands-wrapper${RESET}\n\n"

INSTALL_CWD="$(pwd)"
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

TMP_DIR=""
cleanup() {
    if [ -n "$TMP_DIR" ] && [ -d "$TMP_DIR" ]; then
        rm -rf "$TMP_DIR"
    fi
}
trap cleanup EXIT

start_step "Checking Python and pip availability"
if ! command -v python3 >/dev/null 2>&1; then
    die "python3 was not found in PATH."
fi
if ! python3 -m pip --version >/dev/null 2>&1; then
    die "python3 is available but pip is missing or broken."
fi
step_ok

start_step "Preparing installation source"
LOCAL_SOURCE_ROOT=""
if is_commands_wrapper_source_root "$SCRIPT_REPO_ROOT"; then
    LOCAL_SOURCE_ROOT="$SCRIPT_REPO_ROOT"
elif is_commands_wrapper_source_root "$INSTALL_CWD"; then
    LOCAL_SOURCE_ROOT="$INSTALL_CWD"
fi

if [ -n "$LOCAL_SOURCE_ROOT" ]; then
    cd "$LOCAL_SOURCE_ROOT"
else
    if ! command -v curl >/dev/null 2>&1; then
        die "curl was not found and remote installation requires it."
    fi
    if ! command -v tar >/dev/null 2>&1; then
        die "tar was not found and remote installation requires it."
    fi
    if ! command -v mktemp >/dev/null 2>&1; then
        die "mktemp not found (required for remote install)."
    fi

    TMP_DIR="$(mktemp -d)"
    ARCHIVE_PATH="$TMP_DIR/commands-wrapper.tar.gz"

    if [ -t 1 ]; then
        curl -fSL --progress-bar "$SOURCE_URL" -o "$ARCHIVE_PATH"
    else
        curl -fsSL "$SOURCE_URL" -o "$ARCHIVE_PATH"
    fi

    if [ -n "$SOURCE_SHA256" ]; then
        EXPECTED_SHA256="$(printf '%s' "$SOURCE_SHA256" | tr '[:upper:]' '[:lower:]')"
        if [[ ! "$EXPECTED_SHA256" =~ ^[0-9a-f]{64}$ ]]; then
            die "invalid COMMANDS_WRAPPER_SOURCE_SHA256 value."
        fi

        ACTUAL_SHA256="$(file_sha256 "$ARCHIVE_PATH")"
        if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
            die "source archive checksum mismatch."
        fi
    fi

    tar xzf "$ARCHIVE_PATH" --strip-components=1 -C "$TMP_DIR"
    cd "$TMP_DIR"
fi
step_ok

start_step "Installing/updating package"
if ! run_pip install --upgrade --force-reinstall .; then
    die "pip install failed while installing commands-wrapper."
fi
step_ok

start_step "Resolving command locations"
BIN_DIR="$(scripts_dir_from_python)"
if [ -z "$BIN_DIR" ]; then
    die "failed to determine python scripts directory."
fi
BIN_PATH="$BIN_DIR/$PRIMARY_WRAPPER"
CW_PATH="$BIN_DIR/$SHORT_ALIAS"

if [ ! -f "$BIN_PATH" ]; then
    die "installed binary was not found at '$BIN_PATH'."
fi
chmod +x "$BIN_PATH" >/dev/null 2>&1 || true
step_ok

start_step "Synchronizing wrapper commands"
if ! run_sync_with_retry "$BIN_PATH"; then
    die "automatic wrapper sync failed after retry."
fi
if [ ! -f "$CW_PATH" ]; then
    die "wrapper sync completed but '$CW_PATH' was not generated."
fi
chmod +x "$CW_PATH" >/dev/null 2>&1 || true
step_ok

start_step "Self-healing PATH for global command access"
PATH_RC_FILE=""
if PATH_RC_FILE="$(ensure_path_persistence "$BIN_DIR")"; then
    step_warn "PATH self-heal persisted to $PATH_RC_FILE"
fi
if ! path_has_dir "$BIN_DIR"; then
    export PATH="$BIN_DIR:$PATH"
fi
if ! command -v "$PRIMARY_WRAPPER" >/dev/null 2>&1; then
    die "global access check failed: '$PRIMARY_WRAPPER' is still not discoverable in PATH."
fi
if ! command -v "$SHORT_ALIAS" >/dev/null 2>&1; then
    die "global access check failed: '$SHORT_ALIAS' is still not discoverable in PATH."
fi
step_ok

start_step "Ensuring global command config exists"
USER_CONFIG_DIR="$(user_config_dir_from_python)"
if [ -z "$USER_CONFIG_DIR" ]; then
    die "failed to determine user config directory."
fi
mkdir -p "$USER_CONFIG_DIR"
if [ ! -f "$USER_CONFIG_DIR/commands.yaml" ] && [ ! -f "$USER_CONFIG_DIR/commands.yml" ]; then
    printf '%s\n' \
        '# command-name:' \
        '#   description: "What this command does"' \
        '#   steps 60:' \
        '#     - command: "shell command here"' \
        '#     - send: "text to type into process"' \
        '#     - press_key: "enter"' \
        '#     - wait: "2"' \
        > "$USER_CONFIG_DIR/commands.yaml"
fi
step_ok

start_step "Running post-install launch preview"
if [ -z "${CI:-}" ] && [ -t 0 ] && [ -t 1 ]; then
    "$BIN_PATH"
else
    if ! "$BIN_PATH" list >/dev/null 2>&1; then
        die "post-install verification failed: '$PRIMARY_WRAPPER list' returned a non-zero exit code."
    fi
fi
step_ok

start_step "Final health check"
if ! "$BIN_PATH" --help >/dev/null 2>&1; then
    die "final health check failed: '$PRIMARY_WRAPPER --help' exited non-zero."
fi
step_ok

printf "\n${GREEN}commands-wrapper is installed and self-healed.${RESET}\n"
printf "${GRAY}Use '${SHORT_ALIAS}' or '${PRIMARY_WRAPPER}' from any directory.${RESET}\n"
