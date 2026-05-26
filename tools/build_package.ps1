$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"
$packageRoot = Join-Path $dist "deriv-over3-package"
$zipPath = Join-Path $dist "deriv-over3-package.zip"

New-Item -ItemType Directory -Force -Path $dist | Out-Null
if (Test-Path $packageRoot) {
    Remove-Item -LiteralPath $packageRoot -Recurse -Force
}
if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null

$items = @(
    "api",
    "analytics",
    "dashboard",
    "exports",
    "risk",
    "strategies",
    "web",
    ".env.example",
    "config.py",
    "Dockerfile",
    "docker-compose.yml",
    "DOWNLOAD_INSTRUCTIONS.md",
    "main.py",
    "README.md",
    "requirements.txt"
)

foreach ($item in $items) {
    $source = Join-Path $root $item
    if (Test-Path $source) {
        Copy-Item -LiteralPath $source -Destination $packageRoot -Recurse
    }
}

Get-ChildItem -Path $packageRoot -Directory -Recurse -Force |
    Where-Object { $_.Name -eq "__pycache__" } |
    Remove-Item -Recurse -Force

Get-ChildItem -Path $packageRoot -File -Recurse -Force |
    Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
    Remove-Item -Force

New-Item -ItemType Directory -Force -Path (Join-Path $packageRoot "database") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $packageRoot "logs") | Out-Null
Set-Content -Path (Join-Path $packageRoot "database/.gitkeep") -Value ""
Set-Content -Path (Join-Path $packageRoot "logs/.gitkeep") -Value ""

Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force
Write-Host "Created $zipPath"
