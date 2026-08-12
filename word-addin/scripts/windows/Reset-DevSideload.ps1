# Clear stale MindGraph WEF cache and register localhost Dev sideload only.
# Run from Windows: powershell -File .\scripts\windows\Reset-DevSideload.ps1
$ErrorActionPreference = 'Stop'

# This file lives in word-addin/scripts/windows/ → repo root is three levels up.
$Root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$Manifest = Join-Path $Root 'manifest.xml'
$DevKey = 'HKCU:\SOFTWARE\Microsoft\Office\16.0\Wef\Developer'
$ProdId = 'a8f3c2e1-4b5d-6e7f-8901-23456789abcd'
$DevId = 'c7b2e9a4-1d3f-4e68-9c05-8f2a6b1d4e70'
$Catalog = 'HKCU:\SOFTWARE\Microsoft\Office\16.0\WEF\TrustedCatalogs\{B1E2F3A4-5C6D-7E8F-9012-3456789ABCDE}'
$WefRoot = Join-Path $env:LOCALAPPDATA 'Microsoft\Office\16.0\Wef'

if (-not (Test-Path -LiteralPath $Manifest)) {
    throw "manifest not found: $Manifest"
}

Write-Host "Closing Word..."
Get-Process -Name WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

if (-not (Test-Path -LiteralPath $DevKey)) {
    New-Item -Path $DevKey -Force | Out-Null
}

foreach ($id in @($ProdId, $DevId)) {
    if (Get-ItemProperty -Path $DevKey -Name $id -ErrorAction SilentlyContinue) {
        Remove-ItemProperty -Path $DevKey -Name $id -Force
        Write-Host "Removed Developer value $id"
    }
    $sub = Join-Path $DevKey $id
    if (Test-Path -LiteralPath $sub) {
        Remove-Item -LiteralPath $sub -Recurse -Force
        Write-Host "Removed Developer subkey $id"
    }
}

if (Test-Path -LiteralPath $Catalog) {
    Remove-Item -LiteralPath $Catalog -Recurse -Force
    Write-Host "Removed production TrustedCatalog"
}

if (Test-Path -LiteralPath $WefRoot) {
    Get-ChildItem -LiteralPath $WefRoot -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'a8f3c2e1|c7b2e9a4|MindGraph|mindgraph' } |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "Cleared $($_.Name)"
        }
    foreach ($name in @('AppCommands', 'AggregatedCache')) {
        Get-ChildItem -LiteralPath $WefRoot -Directory -Filter $name -Recurse -Force -ErrorAction SilentlyContinue |
            ForEach-Object {
                Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
                Write-Host "Cleared folder $($_.FullName)"
            }
    }
}

$manifestPath = (Resolve-Path -LiteralPath $Manifest).Path
New-ItemProperty -Path $DevKey -Name $DevId -Value $manifestPath -PropertyType String -Force | Out-Null
New-ItemProperty -Path $DevKey -Name 'RefreshAddins' -Value 1 -PropertyType DWord -Force | Out-Null

[xml]$xml = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8
Write-Host ""
Write-Host "Dev sideload ready."
Write-Host "  Id:      $($xml.OfficeApp.Id)"
Write-Host "  Version: $($xml.OfficeApp.Version)"
Write-Host "  Name:    $($xml.OfficeApp.DisplayName.DefaultValue)"
Write-Host "  Path:    $manifestPath"
Write-Host ""
Write-Host "Next: npm run dev  (terminal 1), then npm start  (terminal 2)."
Write-Host "Ribbon tab should read: MindGraph Dev"
