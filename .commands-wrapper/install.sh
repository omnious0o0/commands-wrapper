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
FISH_PATH_BLOCK_START='# >>> commands-wrapper fish path >>>'
FISH_PATH_BLOCK_END='# <<< commands-wrapper fish path <<<'

TOTAL_STEPS=9
CURRENT_STEP=0
UI_RUNTIME_READY=0

SOURCE_URL="${COMMANDS_WRAPPER_SOURCE_URL:-https://github.com/omnious0o0/commands-wrapper/archive/refs/heads/main.tar.gz}"
SOURCE_SHA256="${COMMANDS_WRAPPER_SOURCE_SHA256:-}"

ensure_ui_runtime() {
    if [ "$UI_RUNTIME_READY" = "1" ]; then
        return 0
    fi

    if python3 -c "import importlib.util, sys; missing=[p for p in ('rich','pyfiglet') if importlib.util.find_spec(p) is None]; raise SystemExit(1 if missing else 0)" >/dev/null 2>&1
    then
        UI_RUNTIME_READY=1
        return 0
    fi

    if python3 -m pip install rich pyfiglet --break-system-packages >/dev/null 2>&1 || \
        python3 -m pip install rich pyfiglet >/dev/null 2>&1; then
        UI_RUNTIME_READY=1
        return 0
    fi

    return 1
}

ui_render() {
    local mode="$1"
    shift || true

    local ui_code
    ui_code="$(cat <<'PY'
import sys

from rich.console import Console
from rich.panel import Panel
from rich.progress_bar import ProgressBar
import pyfiglet

console = Console()
mode = sys.argv[1]

if mode == "logo":
    logo = pyfiglet.figlet_format("commands-wrapper", font="ansi_shadow")
    console.print(Panel(f"[bold cyan]{logo}[/bold cyan]", border_style="cyan", padding=(0, 2)))
elif mode == "step":
    current = int(sys.argv[2])
    total = int(sys.argv[3])
    label = sys.argv[4]
    console.print(f"[cyan][{current}/{total}][/cyan] [bold]{label}[/bold]")
    console.print(ProgressBar(total=total, completed=current, width=36, complete_style="cyan"))
elif mode == "ok":
    console.print("[green]✓[/green] [green]Done[/green]")
elif mode == "warn":
    console.print(f"[yellow]⚠[/yellow] [yellow]{sys.argv[2]}[/yellow]")
elif mode == "error":
    console.print(f"[red]✗[/red] [red]{sys.argv[2]}[/red]")
elif mode == "info":
    console.print(f"[cyan]{sys.argv[2]}[/cyan]")
elif mode == "detail":
    console.print(f"[dim]{sys.argv[2]}[/dim]")
elif mode == "success-panel":
    version = sys.argv[2]
    body = "\n".join([
        f"[green]✓ commands-wrapper {version} installed[/green]",
        "",
        "[cyan]cw[/cyan]                 launch",
        "[cyan]cw --update[/cyan]        update",
        "[cyan]cw --help[/cyan]          all commands",
    ])
    console.print(Panel(body, border_style="green", padding=(1, 2)))
PY
)"

    python3 -c "$ui_code" "$mode" "$@"
}

ui_emit() {
    local mode="$1"
    shift || true

    local rendered
    if ! rendered="$(ui_render "$mode" "$@" 2>/dev/null)"; then
        return 1
    fi

    if [ -z "$rendered" ]; then
        return 1
    fi

    local probe="${1:-}"
    case "$mode" in
        step|warn|error|info|detail)
            if [ -n "$probe" ] && [[ "$rendered" != *"$probe"* ]]; then
                return 1
            fi
            ;;
        ok)
            if [[ "$rendered" != *"Done"* ]] && [[ "$rendered" != *"✓"* ]]; then
                return 1
            fi
            ;;
        success-panel)
            if [[ "$rendered" != *"cw --update"* ]]; then
                return 1
            fi
            ;;
    esac

    printf '%s\n' "$rendered"
    return 0
}

print_logo() {
    if ! ui_emit logo; then
        printf "${BLUE}commands-wrapper${RESET}\n"
    fi
}

draw_progress() {
    local label="$1"
    if ! ui_emit step "$CURRENT_STEP" "$TOTAL_STEPS" "$label"; then
        printf "${BLUE}[%d/%d]${RESET} %s\n" "$CURRENT_STEP" "$TOTAL_STEPS" "$label"
    fi
}

start_step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    draw_progress "$1"
}

step_ok() {
    if ! ui_emit ok; then
        printf "${GREEN}OK${RESET}\n"
    fi
}

step_warn() {
    if ! ui_emit warn "$1"; then
        printf "${YELLOW}WARN:${RESET} %s\n" "$1"
    fi
}

die() {
    if [ "$UI_RUNTIME_READY" = "1" ] && ui_emit error "$1" >&2; then
        :
    else
        printf "${RED}ERROR:${RESET} %s\n" "$1" >&2
    fi
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

resolved_command_path() {
    local command_name="$1"
    type -P "$command_name" 2>/dev/null || true
}

assert_global_command_path() {
    local command_name="$1"
    local expected_dir="$2"
    local resolved
    resolved="$(resolved_command_path "$command_name")"
    if [ -z "$resolved" ]; then
        die "global access check failed: '$command_name' is not discoverable in PATH."
    fi

    local resolved_dir
    resolved_dir="$(dirname "$resolved")"
    if [ "$resolved_dir" != "$expected_dir" ]; then
        die "global access check failed: '$command_name' resolves to '$resolved' instead of '$expected_dir'."
    fi
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
    build_updated_block_content "$PATH_BLOCK_START" "$PATH_BLOCK_END" "$block"
}

build_updated_fish_path_block_content() {
    local block="$1"
    build_updated_block_content "$FISH_PATH_BLOCK_START" "$FISH_PATH_BLOCK_END" "$block"
}

build_updated_block_content() {
    local start_marker="$1"
    local end_marker="$2"
    local block="$3"
    python3 - "$start_marker" "$end_marker" "$block" <<'PY'
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

fish_path_block_for_bin_dir() {
    local bin_dir="$1"
    printf '%s\n' \
        "$FISH_PATH_BLOCK_START" \
        "if test -d \"$bin_dir\"" \
        "    if not contains \"$bin_dir\" \$PATH" \
        "        set -gx PATH \"$bin_dir\" \$PATH" \
        "    end" \
        "end" \
        "$FISH_PATH_BLOCK_END"
}

append_fish_path_block() {
    local fish_conf_path="$1"
    local block="$2"
    local existing=""

    if [ -f "$fish_conf_path" ]; then
        if ! existing="$(<"$fish_conf_path")"; then
            existing=""
        fi
    fi

    local parent
    parent="$(dirname "$fish_conf_path")"
    if [ -n "$parent" ]; then
        mkdir -p "$parent" || return 1
    fi

    local updated
    if ! updated="$(printf '%s' "$existing" | build_updated_fish_path_block_content "$block")"; then
        return 1
    fi

    if [ "$updated" = "$existing" ]; then
        return 0
    fi

    printf '%s' "$updated" > "$fish_conf_path" || return 1
    return 0
}

ensure_fish_path_persistence() {
    local bin_dir="$1"
    local fish_conf_path="$HOME/.config/fish/conf.d/commands-wrapper.fish"
    local fish_block
    fish_block="$(fish_path_block_for_bin_dir "$bin_dir")"

    if append_fish_path_block "$fish_conf_path" "$fish_block"; then
        printf '%s\n' "$fish_conf_path"
        return 0
    fi

    return 1
}

installed_package_version() {
    python3 -m pip show commands-wrapper 2>/dev/null | python3 - <<'PY'
import sys

for line in sys.stdin:
    if line.startswith('Version:'):
        print(line.split(':', 1)[1].strip())
        break
PY
}

project_version_from_pyproject() {
    local pyproject_path="$1"
    python3 - "$pyproject_path" <<'PY'
import pathlib
import re
import sys

pyproject_path = pathlib.Path(sys.argv[1])
if not pyproject_path.is_file():
    sys.exit(0)

text = pyproject_path.read_text(encoding='utf-8', errors='replace')

try:
    import tomllib  # type: ignore[attr-defined]
except Exception:
    tomllib = None

version = None
if tomllib is not None:
    try:
        data = tomllib.loads(text)
    except Exception:
        data = {}
    project = data.get('project') if isinstance(data, dict) else None
    if isinstance(project, dict):
        value = project.get('version')
        if isinstance(value, str) and value.strip():
            version = value.strip()

if version is None:
    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('['):
            in_project = stripped == '[project]'
            continue
        if not in_project:
            continue
        match = re.match(r'^version\s*=\s*["\']([^"\']+)["\']\s*$', stripped)
        if match:
            version = match.group(1).strip()
            break

if version:
    print(version)
PY
}

compare_versions() {
    local left="$1"
    local right="$2"
    python3 - "$left" "$right" <<'PY'
import sys

left = sys.argv[1]
right = sys.argv[2]

try:
    from packaging.version import Version

    left_v = Version(left)
    right_v = Version(right)
except Exception:
    if left == right:
        print('eq')
        raise SystemExit(0)
    print('unknown')
    raise SystemExit(0)

if left_v == right_v:
    print('eq')
elif left_v > right_v:
    print('gt')
else:
    print('lt')
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
        ui_emit warn "Sync attempt output:" || printf '%s\n' "Sync attempt output:"
        while IFS= read -r log_line; do
            ui_emit detail "$log_line" || printf '%s\n' "$log_line"
        done < "$sync_log_first"
    fi

    if [ -f "$sync_log_second" ]; then
        ui_emit warn "Retry sync output:" || printf '%s\n' "Retry sync output:"
        while IFS= read -r log_line; do
            ui_emit detail "$log_line" || printf '%s\n' "$log_line"
        done < "$sync_log_second"
    fi

    rm -f "$sync_log_first" "$sync_log_second"
    return 1
}

if ! command -v python3 >/dev/null 2>&1; then
    printf "${RED}ERROR:${RESET} python3 was not found in PATH.\n" >&2
    exit 1
fi
if ! python3 -m pip --version >/dev/null 2>&1; then
    printf "${RED}ERROR:${RESET} python3 is available but pip is missing or broken.\n" >&2
    exit 1
fi
if ! ensure_ui_runtime; then
    printf "${RED}ERROR:${RESET} failed to install installer UI dependencies (rich, pyfiglet).\n" >&2
    exit 1
fi

print_logo
ui_emit info "Installing commands-wrapper" || printf "${BLUE}Installing commands-wrapper${RESET}\n"

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

TARGET_VERSION="$(project_version_from_pyproject "$(pwd)/pyproject.toml" || true)"
INSTALLED_VERSION="$(installed_package_version || true)"

start_step "Installing/updating package"
if [ -n "$INSTALLED_VERSION" ] && [ -n "$TARGET_VERSION" ]; then
    VERSION_RELATION="$(compare_versions "$INSTALLED_VERSION" "$TARGET_VERSION")"
    if [ "$VERSION_RELATION" = "eq" ]; then
        step_warn "commands-wrapper $INSTALLED_VERSION is already installed; skipping package reinstall."
    elif [ "$VERSION_RELATION" = "gt" ]; then
        step_warn "installed version $INSTALLED_VERSION is newer than source $TARGET_VERSION; skipping downgrade."
    else
        if ! run_pip install --upgrade .; then
            die "pip install failed while installing commands-wrapper."
        fi
    fi
else
    if ! run_pip install --upgrade .; then
        die "pip install failed while installing commands-wrapper."
    fi
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
FISH_PATH_FILE=""
if FISH_PATH_FILE="$(ensure_fish_path_persistence "$BIN_DIR")"; then
    step_warn "Fish PATH self-heal persisted to $FISH_PATH_FILE"
fi
if ! path_has_dir "$BIN_DIR"; then
    export PATH="$BIN_DIR:$PATH"
fi
assert_global_command_path "$PRIMARY_WRAPPER" "$BIN_DIR"
assert_global_command_path "$SHORT_ALIAS" "$BIN_DIR"
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

INSTALLED_AFTER="$(installed_package_version || true)"
if [ -z "$INSTALLED_AFTER" ]; then
    INSTALLED_AFTER="installed"
fi
if ! ui_emit success-panel "$INSTALLED_AFTER"; then
    printf "${GREEN}commands-wrapper is installed and self-healed.${RESET}\n"
fi
