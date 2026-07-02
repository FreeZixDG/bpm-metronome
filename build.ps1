$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectRoot ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$MainScript = Join-Path $ProjectRoot "main.py"
$AppName = "BNM-Metronome"
$AppDataDir = Join-Path $env:APPDATA "BNM Metronome"
$MetrosDir = Join-Path $AppDataDir "metros"
$LocalMetrosDir = Join-Path $ProjectRoot "metros"
$IconDir = Join-Path $ProjectRoot "icon"
$GeneratedIconFile = Join-Path $ProjectRoot "build\app-icon.ico"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList
    )

    & $FilePath @ArgumentList

    if ($LASTEXITCODE -ne 0) {
        throw "La commande a echoue ($LASTEXITCODE): $FilePath $($ArgumentList -join ' ')"
    }
}

function Get-AppIconFile {
    if (-not (Test-Path $IconDir)) {
        Write-Warning "Dossier icon introuvable, l'executable sera cree sans icone personnalisee."
        return $null
    }

    $IconCandidates = Get-ChildItem -Path $IconDir -File | Where-Object {
        $_.Extension -iin @(".ico", ".png", ".jpg", ".jpeg", ".bmp")
    } | Sort-Object @{ Expression = { if ($_.Extension -ieq ".ico") { 0 } else { 1 } } }, Name

    if (-not $IconCandidates) {
        Write-Warning "Aucune image trouvee dans icon, l'executable sera cree sans icone personnalisee."
        return $null
    }

    $SourceIcon = $IconCandidates[0]

    if ($SourceIcon.Extension -ieq ".ico") {
        return $SourceIcon.FullName
    }

    Write-Host "Conversion de l'image d'icone en .ico..."
    $null = Invoke-Checked $PythonExe @("-m", "pip", "install", "--upgrade", "pillow")

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $GeneratedIconFile) | Out-Null

    $ConvertScript = Join-Path $ProjectRoot "build\convert_icon.py"
    @"
from pathlib import Path
from PIL import Image

source = Path(r'''$($SourceIcon.FullName)''')
destination = Path(r'''$GeneratedIconFile''')
destination.parent.mkdir(parents=True, exist_ok=True)

with Image.open(source) as image:
    image = image.convert("RGBA")
    image.save(destination, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
"@ | Set-Content -Path $ConvertScript -Encoding UTF8

    $null = Invoke-Checked $PythonExe @($ConvertScript)

    return $GeneratedIconFile
}

if (-not (Test-Path $MainScript)) {
    throw "main.py introuvable: $MainScript"
}

if (-not $env:APPDATA) {
    throw "La variable APPDATA est introuvable."
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "Creation de l'environnement virtuel..."
    $PythonLauncher = Get-Command py -ErrorAction SilentlyContinue

    if ($PythonLauncher) {
        Invoke-Checked "py" @("-3", "-m", "venv", $VenvDir)
    }
    else {
        Invoke-Checked "python" @("-m", "venv", $VenvDir)
    }
}

if (-not (Test-Path $PythonExe)) {
    throw "Python introuvable dans l'environnement virtuel: $PythonExe"
}

Write-Host "Mise a jour de pip et installation de PyInstaller..."
& $PythonExe -m pip --version | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "Installation de pip dans l'environnement virtuel..."
    Invoke-Checked $PythonExe @("-m", "ensurepip", "--upgrade")
}

Invoke-Checked $PythonExe @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked $PythonExe @("-m", "pip", "install", "--upgrade", "pyinstaller")

Write-Host "Preparation du dossier AppData..."
New-Item -ItemType Directory -Force -Path $MetrosDir | Out-Null

if (Test-Path $LocalMetrosDir) {
    Write-Host "Copie des WAV/index existants vers AppData si absents..."
    Get-ChildItem -Path $LocalMetrosDir -File | Where-Object {
        $_.Extension -ieq ".wav" -or $_.Name -ieq "index.json"
    } | ForEach-Object {
        $Destination = Join-Path $MetrosDir $_.Name

        if (-not (Test-Path $Destination)) {
            Copy-Item -Path $_.FullName -Destination $Destination
        }
    }
}

Write-Host "Build de l'executable..."
$IconFile = Get-AppIconFile

$PyInstallerArgs = @(
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name",
    $AppName
)

if ($IconFile) {
    $PyInstallerArgs += @("--icon", $IconFile)
}

$PyInstallerArgs += $MainScript

Invoke-Checked $PythonExe $PyInstallerArgs

$ExePath = Join-Path $ProjectRoot "dist\$AppName.exe"

Write-Host ""
Write-Host "Build termine."
Write-Host "Executable : $ExePath"
Write-Host "Donnees    : $MetrosDir"
