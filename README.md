# commands-wrapper

`commands-wrapper` wraps multi-step shell sequences into a single named command.

## OS support

- ✅ Linux
- ✅ macOS
- ✅ Windows (PowerShell + CMD wrappers)

Generated wrappers:
- Linux/macOS: `cw`, `command-wrapper`, and command-name shims in `~/.local/bin`
- Windows: `.cmd` and `.ps1` shims in `%APPDATA%\Python\...\Scripts`

## Installation

### Linux / macOS

```bash
curl -sSL https://raw.githubusercontent.com/omnious0o0/commands-wrapper/main/.commands-wrapper/install.sh | bash
```

### Windows (PowerShell)

```powershell
iwr -useb https://raw.githubusercontent.com/omnious0o0/commands-wrapper/main/.commands-wrapper/install.ps1 | iex
```

### pip (all OS)

```bash
python -m pip install commands-wrapper
```

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
