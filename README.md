# commands-wrapper

## What it does

commands-wrapper wraps multi-step shell sequences into a single named command.

It can be used to simply rename commands, or craft a command that performs multiple commands and steps using a single named command.

## Usage examples

How I personally like to use it:

1. renaming a command
instead of `cd <directory path>`, I make a simple command like `OAA` to navigate to that directory without me having to manually type the entire path or even memorize it.

2. crafting a command


## Installation

### Linux / macOS

```bash
curl -fsSL -o install.sh https://raw.githubusercontent.com/omnious0o0/commands-wrapper/main/.commands-wrapper/install.sh
bash install.sh
rm -f install.sh
```

If your environment requires stricter controls, review `install.sh` before running it.

Optional environment variables for the shell installer:
- `COMMANDS_WRAPPER_SOURCE_URL` to override the source tarball URL.
- `COMMANDS_WRAPPER_SOURCE_SHA256` to enforce SHA-256 verification of that tarball.

### Windows (PowerShell)

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/omnious0o0/commands-wrapper/main/.commands-wrapper/install.ps1" -OutFile "install.ps1"
powershell -ExecutionPolicy Bypass -File .\install.ps1
Remove-Item .\install.ps1
```

Optional environment variables for the PowerShell installer:
- `COMMANDS_WRAPPER_SOURCE_URL` to override the source URL passed to `pip install`.
- `COMMANDS_WRAPPER_SOURCE_SHA256` to enforce SHA-256 verification when a remote archive is downloaded first.

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

The TUI opens directly into your command list for quick editing:
- `+ Add new command` is always shown at the top.
- Press `Enter` on any command row to rename it, edit metadata, edit steps, or delete it.
- Existing steps support direct content editing (not just move/delete).
- `Refresh list` and `Exit` are available in the same screen.

Command definitions are discovered from:
- Current working directory (`commands.yaml`, `commands.yml`, local `.commands-wrapper/*.{yml,yaml}`, and local `commands-wrapper/*.{yml,yaml}`)
- User config directories (`%APPDATA%\commands-wrapper` on Windows, `$XDG_CONFIG_HOME/commands-wrapper` or `~/.config/commands-wrapper` on Linux/macOS, plus legacy `~/.commands-wrapper`)

When command names overlap, local project definitions take precedence over user/global definitions.

New commands are written to your user config path by default so they persist across directories and restarts.
Set `COMMANDS_WRAPPER_PREFER_LOCAL_WRITE=1` if you want new commands to target the current directory config file first.

### YAML format

```yaml
command-name:
  description: "Description of the command"
  steps 60:
    - command: "command to run"
    - send: "text to send to the command"
    - press_key: "key to press"
    - wait: "time to wait"
```

`cd` commands are handled specially:
- `- command: "cd /some/path"` updates the working directory for following steps.
- Running `commands-wrapper <name>` directly still opens an interactive shell for
  single-`cd` wrappers.
- Running generated wrapper executables stores the `cd` target for the next wrapper
  command in the same shell process, so chains like `oc && dev` work without token loss.
- With `eval "$(commands-wrapper hook)"` enabled, single-`cd` wrappers change the
  current shell directory directly.

Example:

```yaml
system --update:
  description: "Quick system update"
  steps 60:
    - command: "sudo apt-get update && sudo apt-get upgrade -y"
```

Avoid storing secrets (passwords, tokens, keys) in command YAML files. Prefer interactive prompts or environment-based secrets.
Set `COMMANDS_WRAPPER_REDACT_COMMAND_OUTPUT=1` to redact likely secret values from printed command previews and command-failure messages.

## Commands

> Tip: `cw` is a generated wrapper command (shim) for `commands-wrapper`

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

# multi-word names
commands-wrapper remove "command name"
```

### Wrapper sync

Wrapper generation and cleanup are automatic whenever commands-wrapper runs or when
you add/edit/remove commands.

Automatic sync keeps wrappers up to date but does not prune stale wrappers. Use `commands-wrapper sync`
when you want an explicit stale-wrapper cleanup pass.

If a generated naked wrapper name conflicts with an existing command on your `PATH`,
commands-wrapper skips that wrapper and prints a warning. Use:

```bash
cw <command-name>
commands-wrapper <command-name>
```

Command matching is case-insensitive. Commands that differ only by case (for example `Foo` and `foo`) are rejected to avoid ambiguity.
For naked wrappers on case-sensitive filesystems, commands that contain uppercase letters also generate a preserved-case alias wrapper (for example both `oaa` and `OAA`).

### Update

```bash
commands-wrapper update
commands-wrapper upd
```

Optional environment variables for update:
- `COMMANDS_WRAPPER_UPDATE_URL` to override the update source URL.
- `COMMANDS_WRAPPER_UPDATE_SHA256` to enforce SHA-256 verification before install.

### Hook output for shell init

```bash
commands-wrapper hook
```

On POSIX shells, hook output now uses shell functions for wrapper names that are
valid function identifiers. This allows single-`cd` wrappers to change the current
shell directory directly (instead of opening a nested shell), so chaining like
`oc && dev` works as expected after the hook is loaded.

Typical shell init usage:

```bash
eval "$(commands-wrapper hook)"
```

Wrapper names that are not valid shell function identifiers remain aliases.

### Uninstall

```bash
commands-wrapper --uninstall
```

## License

[MIT](LICENSE)
