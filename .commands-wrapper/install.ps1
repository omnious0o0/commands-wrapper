$ErrorActionPreference = "Stop"

function Invoke-Python {
    param([string[]]$Args)

    $pyExitCode = $null
    $pythonExitCode = $null

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Args
        $pyExitCode = $LASTEXITCODE
        if ($pyExitCode -eq 0) {
            return
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python @Args
        $pythonExitCode = $LASTEXITCODE
        if ($pythonExitCode -eq 0) {
            return
        }
    }

    if ($pyExitCode -ne $null -and $pythonExitCode -ne $null) {
        throw "Both 'py -3' (exit $pyExitCode) and 'python' (exit $pythonExitCode) failed."
    }
    if ($pyExitCode -ne $null) {
        throw "'py -3' failed with exit code $pyExitCode."
    }
    if ($pythonExitCode -ne $null) {
        throw "'python' failed with exit code $pythonExitCode."
    }

    throw "Python 3 was not found in PATH."
}

$repoRoot = $null
if ($MyInvocation.MyCommand.Path) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    if ($scriptDir) {
        $repoRoot = Split-Path -Parent $scriptDir
    }
}

$cwdRoot = (Get-Location).Path
$localProject = $null
if ($repoRoot) {
    $localProject = Join-Path $repoRoot "pyproject.toml"
}

if ($localProject -and (Test-Path $localProject)) {
    Invoke-Python @("-m", "pip", "install", $repoRoot)
} elseif (Test-Path (Join-Path $cwdRoot "pyproject.toml")) {
    Invoke-Python @("-m", "pip", "install", $cwdRoot)
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

$syncWarning = "Installed, but wrapper sync needs a new shell session."
try {
    commands-wrapper sync | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host $syncWarning -ForegroundColor Yellow
    }
} catch {
    Write-Host $syncWarning -ForegroundColor Yellow
}

Write-Host "commands-wrapper installed." -ForegroundColor Green
Write-Host "Run 'commands-wrapper --help' to get started." -ForegroundColor Gray
