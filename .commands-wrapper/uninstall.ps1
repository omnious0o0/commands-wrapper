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

$syncWarning = "Wrapper cleanup failed; continuing package uninstall."
try {
    commands-wrapper sync --uninstall | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host $syncWarning -ForegroundColor Yellow
    }
} catch {
    Write-Host $syncWarning -ForegroundColor Yellow
}

Invoke-Python @("-m", "pip", "uninstall", "commands-wrapper", "-y")

Write-Host "commands-wrapper uninstalled." -ForegroundColor Green
