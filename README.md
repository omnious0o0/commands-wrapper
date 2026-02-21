# commands-wrapper

commands-wrapper lets you wrap multi-step shell sequences into a single named command.

It's simple to interact with, and very powerful for automating repetitive tasks.

## installation

**One-liner:**
```bash
curl -sSL https://raw.githubusercontent.com/omnious0o0/commands-wrapper/main/.commands-wrapper/install.sh | bash
```

## usage

### Interactive CLI (Quick & Easy)

```bash
commands-wrapper configure
```

**IMPORTANT:** To use the commands, you have 2 options:
- <command-name> # make sure it doesn't conflict with any other command.
- command-wrapper <command-name> # or `cw <command-name>` This ensures there are no conflicts.

### YAML format
```yaml
command-name:
  description: "Description of the command" # required
  steps <NUM>: # <NUM> is timeout in seconds (optional)
    - command: "command to run" # required
    - send: "text to send to the command" # optional
    - press_key: "key to press" # optional
    - wait: "time to wait" # optional
```

example:
```yaml
system --update:
  description: "Quick system update"
  steps 60:
    - command: "sudo apt-get update && sudo apt-get upgrade -y"
    - send: "<sudo-password>"
```

## commands

> **TIP:** instead of using `commands-wrapper` you can use `cw`

**Interactive configurator (add/edit/remove):**
```bash
commands-wrapper configure
```

---

**Add a command via stdin:**
```bash
commands-wrapper add --yaml <<EOF
command-name:
  description: "..."
  steps:
    - command: "..."
    - send: "..."
    ...
EOF
```

---

**List commands:**
```bash
commands-wrapper list # or `ls`
```

**Remove a command:**
```bash
commands-wrapper remove <command-name> # or `rm <command-name>`
```

**Install / uninstall:**
```bash
commands-wrapper --install
commands-wrapper --uninstall
```

---

**Help:**
```bash
commands-wrapper --help
```

## support

If you liked commands-wrapper, please consider starring the repo, and dropping a follow for more stuff like this :)  
It takes less than a minute and will help a lot ❤️  

If you want to show extra love, consider *[buying me a coffee](https://buymeacoffee.com/specter0o0)*! ☕

[![alt text](https://imgs.search.brave.com/FolmlC7tneei1JY_QhD9teOLwsU3rivglA3z2wWgJL8/rs:fit:860:0:0:0/g:ce/aHR0cHM6Ly93aG9w/LmNvbS9ibG9nL2Nv/bnRlbnQvaW1hZ2Vz/L3NpemUvdzIwMDAv/MjAyNC8wNi9XaGF0/LWlzLUJ1eS1NZS1h/LUNvZmZlZS53ZWJw)](https://buymeacoffee.com/specter0o0)
