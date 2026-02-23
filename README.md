# commands-wrapper

`commands-wrapper` wraps multi-step shell sequences into a single named command.

## OS support

- ✅ Linux
- ✅ macOS
- ✅ Windows (PowerShell + CMD wrappers)

Generated wrappers:
- Linux/macOS: `cw`, `command-wrapper`, and command-name shims in your Python user `bin` directory (commonly `~/.local/bin`)
- Windows: `.cmd` and `.ps1` shims in your Python user `Scripts` directory

## Installation

### Linux / macOS

```bash
curl -sSL https://raw.githubusercontent.com/omnious0o0/commands-wrapper/main/.commands-wrapper/install.sh | bash
```

If your environment requires stricter controls, download and review the script before executing it.

### Windows (PowerShell)

```powershell
iwr -useb https://raw.githubusercontent.com/omnious0o0/commands-wrapper/main/.commands-wrapper/install.ps1 | iex
```

### pip (all OS, from GitHub source)

```bash
python -m pip install "commands-wrapper @ https://github.com/omnious0o0/commands-wrapper/archive/refs/heads/main.tar.gz"
```

`commands-wrapper` is currently distributed from GitHub source (not PyPI).

## Usage

### Interactive mode

```bash
commands-wrapper configure
```

If a full TUI is unavailable in the current shell, the command falls back to non-interactive guidance.

### YAML format

```yaml
command-name:
  description: "Description of the command"
  steps <NUM>:
    - command: "command to run"
    - send: "text to send to the command"
    - press_key: "key to press"
    - wait: "time to wait"
```

`cd` commands are handled specially:
- `- command: "cd /some/path"` updates the working directory for following steps.
- If a wrapper contains only a single `cd` step and runs in an interactive terminal,
  commands-wrapper opens a shell in that directory.

Example:

```yaml
system --update:
  description: "Quick system update"
  steps 60:
    - command: "sudo apt-get update && sudo apt-get upgrade -y"
    - send: "<sudo-password>"
```

## Commands

> Tip: `cw` is an alias wrapper for `commands-wrapper`

### Configure

```bash
commands-wrapper configure
```

### Add from stdin

```bash
commands-wrapper add --yaml <<EOF
command-name:
  description: "..."
  steps:
    - command: "..."
EOF
```

### List

```bash
commands-wrapper list
```

### Remove

```bash
commands-wrapper remove <command-name>
```

### Sync wrappers

```bash
commands-wrapper sync
commands-wrapper sync --uninstall
```

If a generated naked wrapper name conflicts with an existing command on your `PATH`,
commands-wrapper skips that wrapper and prints a warning. Use:

```bash
cw <command-name>
commands-wrapper <command-name>
```

### Update

```bash
commands-wrapper update
commands-wrapper upd
```

### Hook output for shell init

```bash
commands-wrapper hook
```

### Uninstall

```bash
commands-wrapper --uninstall
```

## License

[MIT](LICENSE)
