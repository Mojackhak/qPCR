Param(
    [switch]$full = $false,       
    [switch]$no_onefile = $false  
)

$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$APP  = Join-Path $ROOT "gui\app.py"
$ENV  = "qPCR_pack"

$cmd = @("python", $APP, "--build")
if (-not $full) { $cmd += "--slim" }
if (-not $no_onefile) { $cmd += "--onefile" }

Write-Host "[INFO] Running: conda run -n $ENV $($cmd -join ' ')"
conda run -n $ENV @cmd


$dist = Join-Path $ROOT "dist"
if (Test-Path $dist) { Start-Process $dist }
