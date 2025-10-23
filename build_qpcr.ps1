# Requires: Windows PowerShell 5+ or PowerShell 7+
# Goal: Build a small Windows GUI executable for the qPCR app from the repository.
# Strategy:
#   1) Create isolated venv and install minimal dependencies.
#   2) Auto-detect entry script and GUI toolkit (Tkinter / PyQt / PySide / wx / PySimpleGUI).
#   3) Prefer Nuitka onefile build with compression (smaller). Fallback to PyInstaller + optional UPX.
# Notes:
#   - All comments are in English as requested.
#   - Default repo path is your provided local path; override via -RepoRoot if needed.

param(
    [string]$RepoRoot = "F:\GitHub\anipose_m\Mojackhak\qPCR",
    [ValidateSet('Nuitka','PyInstaller')]
    [string]$Builder = 'Nuitka',
    [switch]$OneFile,         # default: on; can disable via -OneFile:$false
    [switch]$NoConsole,       # default: on for GUI
    [string]$Entry = ""       # optional explicit entry script path; default: auto-detect
)

# --------- Strict settings ----------
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# --------- Helper: log utility ----------
function Say([string]$msg) {
    Write-Host "[build]" -NoNewline -ForegroundColor Cyan
    Write-Host " $msg"
}

# --------- Defaults ----------
if (-not $OneFile.IsPresent) { $OneFile = $true }
if (-not $NoConsole.IsPresent) { $NoConsole = $true }

# --------- Resolve paths ----------
$RepoRoot = (Resolve-Path $RepoRoot).Path
$workRoot = Join-Path $RepoRoot ".build"
$venvPath = Join-Path $workRoot "venv"
$distRoot = Join-Path $workRoot "dist"
$distNuitka = Join-Path $distRoot "nuitka"
$distPyInstaller = Join-Path $distRoot "pyinstaller"
New-Item -ItemType Directory -Force -Path $workRoot,$distRoot,$distNuitka,$distPyInstaller | Out-Null

Say "Repository: $RepoRoot"

# --------- Locate Python launcher (robust) ----------
# Do NOT store "py -3.11" in a single string. Keep executable and args separate.
$pythonExe = $null
$pyVerSwitch = @()   # default: no version switch

try {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        # Use Windows Python launcher and pick the latest Python 3 available.
        $pythonExe = $py.Path
        $pyVerSwitch = @("-3")   # more robust than "-3.11"
    } else {
        # Fallback to plain "python" on PATH
        $p = Get-Command python -ErrorAction SilentlyContinue
        if ($p) { $pythonExe = $p.Path } else { $pythonExe = $null }
    }
} catch { $pythonExe = $null }

if (-not $pythonExe) {
    throw "No Python launcher found. Install Python 3.x and ensure 'py' or 'python' is on PATH."
}

Say "Using Python: $pythonExe $($pyVerSwitch -join ' ')"

# --------- Create & activate venv ----------
if (-not (Test-Path $venvPath)) {
    Say "Creating virtual environment..."
    # IMPORTANT: pass args as an array, not a single string
    & $pythonExe @($pyVerSwitch + @("-m","venv",$venvPath))
}

$activate = Join-Path $venvPath "Scripts\Activate.ps1"
. $activate
$env:PYTHONUTF8 = "1"


Say "Upgrading pip/setuptools/wheel..."
python -m pip install --upgrade pip setuptools wheel

# --------- Install project deps (minimal) ----------
# Preference order:
#   1) env\requirements.txt
#   2) requirements.txt at repo root
#   3) auto-generate minimal requirements via pipreqs
$req = $null
if (Test-Path (Join-Path $RepoRoot "env\requirements.txt")) {
    $req = (Join-Path $RepoRoot "env\requirements.txt")
} elseif (Test-Path (Join-Path $RepoRoot "requirements.txt")) {
    $req = (Join-Path $RepoRoot "requirements.txt")
} else {
    Say "No requirements.txt found; generating minimal requirements with pipreqs..."
    python -m pip install --upgrade pipreqs
    # Ignore build and typical non-source folders
    & pipreqs $RepoRoot --force --encoding=utf-8 --ignore ".build,.git,env,venv,dist,build,tests,test"
    $req = (Join-Path $RepoRoot "requirements.txt")
    if (-not (Test-Path $req)) { throw "Failed to generate requirements.txt" }
}

Say "Installing dependencies from: $req"
python -m pip install -r $req

# --------- Auto-detect entry script if not provided ----------
function Get-EntryPoint {
    param([string]$root)

    $candidatesOrdered = @(
        "gui\main.py","gui\app.py","gui\gui.py",
        "main.py","app.py","run.py"
    ) | ForEach-Object { Join-Path $root $_ } | Where-Object { Test-Path $_ }

    if ($candidatesOrdered.Count -gt 0) { return $candidatesOrdered[0] }

    # Last resort: search for __main__ guard
    $allPy = Get-ChildItem -Path $root -Recurse -Filter *.py | Where-Object {
        $_.FullName -notmatch "\\(\.build|venv|env|dist|tests?|\.git)\\"
    }
    foreach ($f in $allPy) {
        if (Select-String -Path $f.FullName -Pattern "__name__\s*==\s*['""]__main__['""]" -Quiet) {
            return $f.FullName
        }
    }
    return $null
}

if ([string]::IsNullOrWhiteSpace($Entry)) {
    $Entry = Get-EntryPoint -root $RepoRoot
    if (-not $Entry) {
        throw "Cannot locate an entry script automatically. Please pass -Entry PATH\TO\script.py"
    }
}
$Entry = (Resolve-Path $Entry).Path
Say "Detected entry: $Entry"

# --------- Detect GUI toolkit to enable correct plugins ----------
$allCode = (Get-ChildItem -Path $RepoRoot -Recurse -Include *.py | `
    Where-Object { $_.FullName -notmatch "\\(\.build|venv|env|dist|tests?|\.git)\\"} | `
    ForEach-Object { Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue }) -join "`n"

$guiType = "unknown"
$guiPlugins = New-Object System.Collections.Generic.List[string]
if ($allCode -match "(?ms)^\s*(import|from)\s+tkinter\b") { $guiType="tkinter"; $guiPlugins.Add("tk-inter") }
elseif ($allCode -match "(?ms)^\s*(import|from)\s+PySide6\b") { $guiType="pyside6"; $guiPlugins.Add("pyside6") }
elseif ($allCode -match "(?ms)^\s*(import|from)\s+PySide2\b") { $guiType="pyside2"; $guiPlugins.Add("pyside2") }
elseif ($allCode -match "(?ms)^\s*(import|from)\s+PyQt6\b") { $guiType="pyqt6"; $guiPlugins.Add("pyqt6") }
elseif ($allCode -match "(?ms)^\s*(import|from)\s+PyQt5\b") { $guiType="pyqt5"; $guiPlugins.Add("pyqt5") }
elseif ($allCode -match "(?ms)^\s*(import|from)\s+wx\b")     { $guiType="wx";      $guiPlugins.Add("wx") }
elseif ($allCode -match "(?ms)^\s*(import|from)\s+PySimpleGUI\b") { $guiType="pysimplegui"; $guiPlugins.Add("tk-inter") }

Say "Detected GUI toolkit: $guiType (plugins: $($guiPlugins -join ', '))"

# --------- Locate icon and data directory (optional) ----------
$iconIco = $null
$iconDir = Join-Path $RepoRoot "icon"
if (Test-Path $iconDir) {
    $iconIco = Get-ChildItem -Path $iconDir -Recurse -Include *.ico -ErrorAction SilentlyContinue | Select-Object -First 1
}
$dataDir = Join-Path $RepoRoot "data"
$hasDataDir = Test-Path $dataDir
if ($iconIco) { Say "Using icon: $($iconIco.FullName)" }
if ($hasDataDir) { Say "Including data dir: $dataDir" }

# --------- Try preferred builder ----------
if ($Builder -eq 'Nuitka') {
    Say "Installing builder: Nuitka (+ zstandard for onefile compression)"
    python -m pip install --upgrade nuitka ordered-set zstandard

    # Compose Nuitka args
    $nArgs = @("-m","nuitka")

    if ($OneFile) { $nArgs += "--onefile" }

    if ($NoConsole) { $nArgs += "--windows-console-mode=disable" }  # hide console for GUI

    # Size optimization knobs
    $nArgs += @("--lto=yes", "--follow-imports", "--remove-output", "--python-flag=no_docstrings")
    $nArgs += "--assume-yes-for-downloads"  # auto-get MinGW/clang if needed
    $nArgs += ("--jobs=" + [Environment]::ProcessorCount)

    # Exclude obvious test modules to reduce size
    $nArgs += @(
        "--nofollow-import-to=*.tests",
        "--nofollow-import-to=tests",
        "--nofollow-import-to=pytest"
    )

    # GUI plugins (tk-inter/pyqt*/pyside*/wx)
    foreach ($p in $guiPlugins) { $nArgs += "--plugin-enable=$p" }

    # Icon and data
    if ($iconIco) { $nArgs += "--windows-icon-from-ico=$($iconIco.FullName)" }
    if ($hasDataDir) { $nArgs += "--include-data-dir=$($dataDir)=data" }

    # Emit logs when console is disabled (debugging without a console)
    $nArgs += @("--force-stdout-spec=%PROGRAM%.out.txt", "--force-stderr-spec=%PROGRAM%.err.txt")

    # Output control
    $nArgs += ("--output-dir=" + $distNuitka)
    $nArgs += "--output-filename=qPCR.exe"

    Say "Building with Nuitka..."
    & python $nArgs $Entry

    $outExe = Join-Path $distNuitka "qPCR.exe"
    if (Test-Path $outExe) {
        $sizeMB = [Math]::Round((Get-Item $outExe).Length / 1MB, 2)
        Say "SUCCESS (Nuitka): $outExe  [$sizeMB MB]"
        Say "Tip: .out.txt / .err.txt will appear next to the EXE if your GUI prints anything."
        exit 0
    } else {
        Say "Nuitka build did not produce an EXE; falling back to PyInstaller..."
        $Builder = 'PyInstaller'
    }
}

# --------- Fallback builder: PyInstaller (+ optional UPX) ----------
if ($Builder -eq 'PyInstaller') {
    Say "Installing builder: PyInstaller"
    python -m pip install --upgrade pyinstaller

    # Detect UPX for extra compression (optional)
    $upx = Get-Command upx.exe -ErrorAction SilentlyContinue
    $upxDir = $null
    if ($upx) { $upxDir = Split-Path -Parent $upx.Path; Say "UPX detected: $upxDir" }

    $piArgs = @("--clean","--name","qPCR")
    if ($OneFile) { $piArgs += "--onefile" } else { $piArgs += "--onedir" }
    if ($NoConsole) { $piArgs += "--noconsole" }

    if ($iconIco) { $piArgs += @("--icon",$iconIco.FullName) }

    # Exclude typical bulky test packages
    $piArgs += @(
        "--exclude-module","pytest",
        "--exclude-module","tests",
        "--exclude-module","numpy.tests",
        "--exclude-module","pandas.tests",
        "--exclude-module","matplotlib.tests",
        "--exclude-module","tkinter.test"
    )

    # Include data directory if present
    if ($hasDataDir) {
        $sep = ";"
        $piArgs += @("--add-data", "$dataDir$sep" + "data")
    }

    if ($upxDir) { $piArgs += @("--upx-dir",$upxDir) }

    $piArgs += @("--distpath",$distPyInstaller, "--workpath", (Join-Path $workRoot "build_pyinstaller"), "--specpath",(Join-Path $workRoot "spec"))

    Say "Building with PyInstaller..."
    & pyinstaller $piArgs $Entry

    # Locate output
    $outExe = if ($OneFile) { Join-Path $distPyInstaller "qPCR.exe" } else { Join-Path (Join-Path $distPyInstaller "qPCR") "qPCR.exe" }
    if (-not (Test-Path $outExe)) {
        # Try the default name based on entry stem
        $stem = [IO.Path]::GetFileNameWithoutExtension($Entry)
        $outExe = if ($OneFile) { Join-Path $distPyInstaller "$stem.exe" } else { Join-Path (Join-Path $distPyInstaller $stem) "$stem.exe" }
    }

    if (Test-Path $outExe) {
        $sizeMB = [Math]::Round((Get-Item $outExe).Length / 1MB, 2)
        Say "SUCCESS (PyInstaller): $outExe  [$sizeMB MB]"
        if (-not $upxDir) {
            Say "Hint: Install UPX and put 'upx.exe' in PATH to shrink further."
        }
        exit 0
    } else {
        throw "PyInstaller build failed; no EXE found under $distPyInstaller"
    }
}
