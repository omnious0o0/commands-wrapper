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

try {
    commands-wrapper sync --uninstall | Out-Null
} catch {
    # Continue: package might already be removed
}

Invoke-Python @("-m", "pip", "uninstall", "commands-wrapper", "-y")

Write-Host "commands-wrapper uninstalled." -ForegroundColor Green
