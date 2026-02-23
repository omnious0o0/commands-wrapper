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

function Get-PythonScriptsDir {
    $code = @'
import os
import site
import sys
import sysconfig

in_venv = getattr(sys, "base_prefix", sys.prefix) != sys.prefix
scripts = None
if in_venv:
    scripts = sysconfig.get_path("scripts")
else:
    scheme = f"{os.name}_user"
    if scheme in sysconfig.get_scheme_names():
        scripts = sysconfig.get_path("scripts", scheme=scheme)

if not scripts:
    scripts = os.path.join(site.USER_BASE or os.path.expanduser("~"), "bin")

print(os.path.abspath(scripts))
'@

    $candidates = @(
        @{ exe = "py"; args = @("-3") },
        @{ exe = "python"; args = @() }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.exe -ErrorAction SilentlyContinue)) {
            continue
        }

        $output = & $candidate.exe @($candidate.args + @("-c", $code)) 2>$null
        if ($LASTEXITCODE -eq 0 -and $output) {
            return ($output | Select-Object -Last 1).ToString().Trim()
        }
    }

    return $null
}

function Resolve-WrapperSyncCommand {
    param([string]$ScriptsDir)

    if (-not $ScriptsDir) {
        return $null
    }

    $candidates = @(
        "commands-wrapper.exe",
        "commands-wrapper",
        "commands-wrapper.cmd",
        "commands-wrapper.ps1"
    )

    foreach ($candidate in $candidates) {
        $path = Join-Path $ScriptsDir $candidate
        if (Test-Path $path) {
            return $path
        }
    }

    return $null
}

$syncWarning = "Wrapper cleanup failed; continuing package uninstall."
$scriptsDir = Get-PythonScriptsDir
$syncCommand = Resolve-WrapperSyncCommand -ScriptsDir $scriptsDir

if ($syncCommand) {
    try {
        & $syncCommand sync --uninstall | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host $syncWarning -ForegroundColor Yellow
        }
    } catch {
        Write-Host $syncWarning -ForegroundColor Yellow
    }
} else {
    Write-Host $syncWarning -ForegroundColor Yellow
}

Invoke-Python @("-m", "pip", "uninstall", "commands-wrapper", "-y")

Write-Host "commands-wrapper uninstalled." -ForegroundColor Green
