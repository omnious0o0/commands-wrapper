$ErrorActionPreference = "Stop"

function Invoke-Python {
    param([string[]]$Args)
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Args
        return
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python @Args
        return
    }
    throw "Python 3 was not found in PATH."
}

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $here
$localProject = Join-Path $repoRoot "pyproject.toml"

if (Test-Path $localProject) {
    Invoke-Python @("-m", "pip", "install", $repoRoot)
} else {
    Invoke-Python @("-m", "pip", "install", "https://github.com/omnious0o0/commands-wrapper/archive/refs/heads/main.tar.gz")
}

$hasYaml = (Test-Path "commands.yaml") -or (Test-Path "commands.yml")
if (-not $hasYaml) {
@'
# command-name:
#   description: "What this command does"
#   steps 60:
#     - command: "shell command here"
#     - send: "text to type into process"
#     - press_key: "enter"
#     - wait: "2"
'@ | Out-File -Encoding utf8 "commands.yaml"
}

try {
    commands-wrapper sync | Out-Null
} catch {
    Write-Host "Installed, but wrapper sync needs a new shell session." -ForegroundColor Yellow
}

Write-Host "commands-wrapper installed." -ForegroundColor Green
Write-Host "Run 'commands-wrapper --help' to get started." -ForegroundColor Gray
