# commands-wrapper

Wraps multi-step shell sequences into a single named command. Use it to chain multiple steps together into one. Steps are like:
    
```bash
    - command: "shell command to run"
    - code.py: "Python code snippet to excute"
    - send: "text to send to the process"
    - press_key: "key to press"
    - wait: "seconds to wait"
```

## Installation

Unix (Linux/macOS/WSL):

```bash
curl -fsSL https://raw.githubusercontent.com/omnious0o0/commands-wrapper/main/.commands-wrapper/install.sh | sh
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/omnious0o0/commands-wrapper/main/.commands-wrapper/install.ps1 | iex
```

## usage

### easy (for humans)

Run interactive TUI using:
```bash
cw # or commands-wrapper
```

This allows you to view all your "wraps", modify them or add new ones.

### AI agents (skill)

If you're an AI agent, configure directly like this:
```bash
commands-wrapper add --yaml <<EOF
command-name:
  description: "..."
  steps:
    - command: "..."
EOF
```
> See `YAML format` below

## YAML format

```yaml
wrap-name: # The name you'll type to run this wrap
  description: "What this command does"
  steps:
    - command: "shell command to run"
    - code.py: "Python code snippet to excute" # only python
    - send: "text to send to the process"
    - press_key: "key to press"
    - wait: "seconds to wait"
    ... # add as much as you want
```

## Commands

```bash
commands-wrapper list 
```

```bash
commands-wrapper remove "command-name" # seppirate by comma for multiple at once
```

```bash
cw <command-name>
commands-wrapper <command-name>
```

```bash
commands-wrapper update # or upd
```
> you can also rerun the install command


```bash
commands-wrapper --uninstall
```

## Support

If you found this project useful, please consider starring the repo and dropping me a follow for more stuff like this :)
It takes less than a minute and helps a lot ❤️

> If you find a bug or unexpected behavior, please report it!

---


**RECOMMENDED:** Check out [commands-wrapper](https://github.com/omnious0o0/commands-wrapper) you and your agent will love it!

---

If you want to show extra love, consider *[buying me a coffee](https://buymeacoffee.com/specter0o0)*! ☕


[![Buy Me a Coffee](https://imgs.search.brave.com/FolmlC7tneei1JY_QhD9teOLwsU3rivglA3z2wWgJL8/rs:fit:860:0:0:0/g:ce/aHR0cHM6Ly93aG9w/LmNvbS9ibG9nL2Nv/bnRlbnQvaW1hZ2Vz/L3NpemUvdzIwMDAv/MjAyNC8wNi9XaGF0/LWlzLUJ1eS1NZS1h/LUNvZmZlZS53ZWJw)](https://buymeacoffee.com/specter0o0)

### Related projects

- [commands-wrapper](https://github.com/omnious0o0/commands-wrapper)
- [extract](https://github.com/omnious0o0/extract)

**And more on [omnious](https://github.com/omnious0o0)!**

## License

[MIT](LICENSE)