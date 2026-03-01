# commands-wrapper

Wraps multi-step shell sequences into a single named command. Use it to rename long commands into short ones, or chain multiple steps together into one.

---

## Installation

```bash
curl -fsSL -o install.sh https://raw.githubusercontent.com/omnious0o0/commands-wrapper/main/.commands-wrapper/install.sh
bash install.sh

# then run it using
cw # or commands-wrapper
```

## Usage

run
```bash
cw # or commands-wrapper
```
to enter interactive mode.

It's very simple, controls are simply:
- `arrow keys` to navigate (alternatively `j` and `k`)
- `enter` to select
- `esc` to exit

From the TUI you can:
- Add a new command (`+ Add new command` is pinned at the top)
- Press `Enter` on any command to rename it, edit its metadata, edit steps, or delete it
- Edit step content directly, not just move or delete
- Refresh the list or exit from the same screen

**Where commands are loaded from:**
- Current directory: `commands.yaml`, `commands.yml`, local `.commands-wrapper/*.{yml,yaml}`, and local `commands-wrapper/*.{yml,yaml}`
- User config: `%APPDATA%\commands-wrapper` on Windows, `$XDG_CONFIG_HOME/commands-wrapper` or `~/.config/commands-wrapper` on Linux/macOS, plus the legacy `~/.commands-wrapper` path

When the same command name exists in both places, the local project definition wins.

New commands are saved to your user config by default so they persist across directories. Set `COMMANDS_WRAPPER_PREFER_LOCAL_WRITE=1` to write to the current directory's config file instead.

By default, local commands found in the current directory are promoted to your user config so they stay available everywhere. Set `COMMANDS_WRAPPER_AUTO_PROMOTE_LOCAL=0` to turn that off.

---

## YAML format

```yaml
command-name:
  description: "What this command does"
  steps:
    - command: "shell command to run"
    - send: "text to send to the process"
    - press_key: "key to press"
    - wait: "seconds to wait"
```

A `cd` step updates the working directory for all steps that follow it. Running a single-`cd` wrapper directly opens an interactive shell at that path. With `eval "$(commands-wrapper hook)"` active, it changes the current shell directory instead, so chaining like `oc && dev` works as expected.

**Example:**

```yaml
system --update:
  description: "Quick system update"
  steps:
    - command: "sudo apt-get update && sudo apt-get upgrade -y"
```

> Avoid storing secrets (passwords, tokens, keys) in YAML files. Use interactive prompts or environment variables instead. Set `COMMANDS_WRAPPER_REDACT_COMMAND_OUTPUT=1` to redact likely secret values from printed output and failure messages.

---

## Commands

> `cw` is a generated shim for `commands-wrapper`

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

### Sync wrappers

Wrapper generation and cleanup happen automatically whenever commands-wrapper runs or when you add, edit, or remove a command. Running `sync` explicitly triggers a stale-wrapper cleanup pass.

```bash
commands-wrapper sync
```

If a generated wrapper name conflicts with an existing command on your `PATH`, commands-wrapper skips that wrapper and prints a warning. In that case, run the command directly with:

```bash
cw <command-name>
commands-wrapper <command-name>
```

Command matching is case-insensitive. Commands that differ only by case (like `Foo` and `foo`) are rejected to avoid ambiguity. On case-sensitive filesystems, commands with uppercase letters also get a preserved-case alias wrapper.

### Update

```bash
commands-wrapper update
commands-wrapper upd
```

**Optional environment variables:**
- `COMMANDS_WRAPPER_UPDATE_URL` — override the update source URL
- `COMMANDS_WRAPPER_UPDATE_SHA256` — enforce SHA-256 verification before install

### Shell hook

```bash
commands-wrapper hook
```

Outputs shell initialization code. Add it to your shell config:

```bash
eval "$(commands-wrapper hook)"
```

On POSIX shells, the hook uses shell functions for valid function identifier names, allowing single-`cd` wrappers to change the current shell directory directly. Wrapper names that are not valid function identifiers are set up as aliases instead.

### Uninstall

```bash
commands-wrapper --uninstall
```

---

## Usage examples

**Shortcut a long path:**

```yaml
oc:
  description: "Open projects folder"
  steps:
    - command: "cd /home/user/Storage/Projects"
```

**Chain steps together:**

```yaml
deploy:
  description: "Build and deploy"
  steps:
    - command: "python build.py"
    - wait: "3"
    - command: "python deploy.py"
```

**With hook enabled, chain commands in one shell:**

```bash
oc && dev  # navigates then starts dev server in the same shell
```

---

## License

[MIT](LICENSE)
