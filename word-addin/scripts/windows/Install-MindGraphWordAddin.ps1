# Register or unregister MindGraph for Word on Windows 10 / 11 (HKCU WEF Developer).
# Copies manifest into LocalAppData so the download zip can be deleted after install.
#
# Install:   windows\Install.cmd  OR  powershell -File .\Install-MindGraphWordAddin.ps1
# Uninstall: windows\Uninstall.cmd  OR  powershell -File .\Install-MindGraphWordAddin.ps1 -Uninstall
param(
    [switch]$Uninstall,
    [switch]$NoLaunchWord
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $env:LOCALAPPDATA 'MindGraph\WordAddin'
$InstalledManifest = Join-Path $InstallDir 'manifest.xml'
$DeveloperKey = 'HKCU:\SOFTWARE\Microsoft\Office\16.0\Wef\Developer'

function Get-AddInId([string]$Path) {
    [xml]$xml = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
    $ns.AddNamespace('o', 'http://schemas.microsoft.com/office/appforoffice/1.1')
    $idNode = $xml.SelectSingleNode('//o:Id', $ns)
    if (-not $idNode -or [string]::IsNullOrWhiteSpace($idNode.InnerText)) {
        throw "Could not read <Id> from $Path"
    }
    return $idNode.InnerText.Trim()
}

function Find-SourceManifest([string]$WindowsScriptDir) {
    $candidates = @(
        (Join-Path (Split-Path -Parent $WindowsScriptDir) 'manifest.xml'),
        (Join-Path $WindowsScriptDir 'manifest.xml'),
        (Join-Path (Split-Path -Parent (Split-Path -Parent $WindowsScriptDir)) 'manifest.xml')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Find-WinWord {
    $fromPath = Get-Command winword.exe -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }
    $candidates = @(
        "${env:ProgramFiles}\Microsoft Office\root\Office16\WINWORD.EXE",
        "${env:ProgramFiles(x86)}\Microsoft Office\root\Office16\WINWORD.EXE",
        "${env:ProgramFiles}\Microsoft Office\Office16\WINWORD.EXE",
        "${env:ProgramFiles(x86)}\Microsoft Office\Office16\WINWORD.EXE"
    )
    foreach ($path in $candidates) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            return $path
        }
    }
    return $null
}

if ($Uninstall) {
    $manifestForId = $null
    if (Test-Path -LiteralPath $InstalledManifest) {
        $manifestForId = $InstalledManifest
    }
    else {
        $manifestForId = Find-SourceManifest $ScriptDir
    }

    $removed = $false
    if ($manifestForId) {
        $addInId = Get-AddInId $manifestForId
        if (Test-Path $DeveloperKey) {
            if (Get-ItemProperty -Path $DeveloperKey -Name $addInId -ErrorAction SilentlyContinue) {
                Remove-ItemProperty -Path $DeveloperKey -Name $addInId -Force
                $removed = $true
                Write-Host "Removed registry entry ($addInId)."
            }
        }
    }
    if (Test-Path -LiteralPath $InstallDir) {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force
        $removed = $true
        Write-Host "Removed $InstallDir"
    }
    if ($removed) {
        Write-Host "Uninstalled MindGraph for Word."
    }
    else {
        Write-Host "MindGraph for Word was not installed for this Windows user."
    }
    return
}

$SourceManifest = Find-SourceManifest $ScriptDir
if (-not $SourceManifest) {
    throw "manifest.xml not found. Unzip the download (README.md + manifest.xml + windows\ + mac\) and run windows\Install.cmd again."
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item -LiteralPath $SourceManifest -Destination $InstalledManifest -Force

$AddInId = Get-AddInId $InstalledManifest
if (-not (Test-Path $DeveloperKey)) {
    New-Item -Path $DeveloperKey -Force | Out-Null
}
New-ItemProperty -Path $DeveloperKey -Name $AddInId -Value $InstalledManifest -PropertyType String -Force | Out-Null

Write-Host "Installed MindGraph for Word (Windows 10 / 11)."
Write-Host "Manifest: $InstalledManifest"
Write-Host "You may delete the download/unzip folder; Word uses the LocalAppData copy."
Write-Host "Open Word -> MindGraph ribbon -> Settings (server, phone, API token)."

if (-not $NoLaunchWord) {
    $wordExe = Find-WinWord
    if ($wordExe) {
        Write-Host "Opening Word..."
        Start-Process -FilePath $wordExe
    }
    else {
        Write-Host "Open Word manually if it did not start."
    }
}
