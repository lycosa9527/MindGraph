# Register MindGraph for Word on Windows 10 / 11.
# 1) Copies manifest to LocalAppData
# 2) WEF Developer registry (office-addin-debugging style)
# 3) Trusted shared-folder catalog (Microsoft network-share sideload docs)
#
# Install:   windows\Install.cmd
# Uninstall: windows\Uninstall.cmd  OR  -Uninstall
param(
    [switch]$Uninstall,
    [switch]$NoLaunchWord
)

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $env:LOCALAPPDATA 'MindGraph\WordAddin'
$InstalledManifest = Join-Path $InstallDir 'manifest.xml'
$DeveloperKey = 'HKCU:\SOFTWARE\Microsoft\Office\16.0\Wef\Developer'
$TrustedCatalogsKey = 'HKCU:\SOFTWARE\Microsoft\Office\16.0\WEF\TrustedCatalogs'
# Stable catalog Id for this product (Show in Menu = Flags 1).
$CatalogGuid = '{B1E2F3A4-5C6D-7E8F-9012-3456789ABCDE}'
$ShareName = 'MindGraphWordAddin'
$DevSideloadId = 'c7b2e9a4-1d3f-4e68-9c05-8f2a6b1d4e70'
$ProdAddInId = 'a8f3c2e1-4b5d-6e7f-8901-23456789abcd'

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

function Test-ManifestAppDomains([string]$Path) {
    [xml]$xml = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
    $ns.AddNamespace('o', 'http://schemas.microsoft.com/office/appforoffice/1.1')
    $nodes = $xml.SelectNodes('//o:AppDomains/o:AppDomain', $ns)
    if (-not $nodes -or $nodes.Count -eq 0) {
        throw "manifest has no AppDomain entries: $Path"
    }
    foreach ($node in $nodes) {
        $value = $node.InnerText.Trim()
        if ($value -match '^https?://[^/]+/.+') {
            throw "Invalid AppDomain (must not include a path): $value"
        }
        if ($value -match 'localhost|127\.0\.0\.1') {
            throw "Invalid AppDomain (loopback not allowed in production install): $value"
        }
    }
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

function Stop-WordForReload {
    $procs = Get-Process -Name WINWORD -ErrorAction SilentlyContinue
    if (-not $procs) {
        return
    }
    Write-Host "Closing Word so it reloads add-in registration..."
    foreach ($proc in $procs) {
        try {
            $proc.CloseMainWindow() | Out-Null
        }
        catch {
            # ignore
        }
    }
    Start-Sleep -Seconds 2
    Get-Process -Name WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

function Clear-MindGraphWefCache {
    $wefRoot = Join-Path $env:LOCALAPPDATA 'Microsoft\Office\16.0\Wef'
    if (-not (Test-Path -LiteralPath $wefRoot)) {
        return
    }
    Get-ChildItem -LiteralPath $wefRoot -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match 'a8f3c2e1|MindGraph' } |
        ForEach-Object {
            try {
                Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            }
            catch {
                # ignore locked files
            }
        }
}

function Remove-TrustedCatalog {
    $key = Join-Path $TrustedCatalogsKey $CatalogGuid
    if (Test-Path -LiteralPath $key) {
        Remove-Item -LiteralPath $key -Recurse -Force
        Write-Host "Removed TrustedCatalog $CatalogGuid"
    }
}

function Remove-HttpsWebsiteCatalogs {
    # HTTPS site roots are not shared-folder catalogs; they break SHARED FOLDER UI.
    if (-not (Test-Path -LiteralPath $TrustedCatalogsKey)) {
        return
    }
    Get-ChildItem -LiteralPath $TrustedCatalogsKey -ErrorAction SilentlyContinue | ForEach-Object {
        $props = Get-ItemProperty -Path $_.PSPath -ErrorAction SilentlyContinue
        $url = [string]$props.Url
        if ($url -match '^https?://') {
            Write-Host "Removing invalid HTTPS TrustedCatalog: $url"
            Remove-Item -LiteralPath $_.PSPath -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-AdminShareUnc([string]$Directory) {
    $resolved = (Resolve-Path -LiteralPath $Directory).Path
    if ($resolved -match '^([A-Za-z]):\\(.*)$') {
        $drive = $Matches[1]
        $rest = $Matches[2]
        # e.g. C:\Users\... → \\localhost\C$\Users\...
        return ('\\localhost\{0}$\{1}' -f $drive, $rest)
    }
    return $null
}

function Ensure-CatalogShare([string]$Directory) {
    $existing = $null
    if (Get-Command Get-SmbShare -ErrorAction SilentlyContinue) {
        $existing = Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue
        if ($existing -and $existing.Path -ne $Directory) {
            Remove-SmbShare -Name $ShareName -Force -ErrorAction SilentlyContinue
            $existing = $null
        }
        if (-not $existing) {
            try {
                New-SmbShare -Name $ShareName -Path $Directory -ReadAccess 'Everyone' -ErrorAction Stop | Out-Null
                $existing = Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue
            }
            catch {
                Write-Host "NOTE: New-SmbShare failed ($($_.Exception.Message)). Trying net share..."
            }
        }
    }
    if ($existing) {
        return "\\$env:COMPUTERNAME\$ShareName"
    }

    # Native net.exe — do not let stderr abort install (cwd may be a UNC from WSL).
    $prev = Get-Location
    try {
        Set-Location $env:SystemRoot
        cmd.exe /c "net share $ShareName /delete >nul 2>nul"
        $create = cmd.exe /c "net share `"$ShareName=$Directory`" /GRANT:Everyone,READ"
        if ($LASTEXITCODE -eq 0) {
            return "\\$env:COMPUTERNAME\$ShareName"
        }
        Write-Host "NOTE: Could not create SMB share ($ShareName): $create"
    }
    finally {
        Set-Location $prev
    }

    # Fallback: admin share UNC (no new share required on most Windows SKUs).
    $adminUnc = Get-AdminShareUnc $Directory
    if ($adminUnc) {
        Write-Host "Using admin-share catalog path: $adminUnc"
        return $adminUnc
    }
    Write-Host "NOTE: No shared-folder catalog. Use Upload My Add-in instead."
    return $null
}

function Register-TrustedCatalog([string]$UncPath) {
    if (-not $UncPath) {
        return
    }
    if (-not (Test-Path -LiteralPath $TrustedCatalogsKey)) {
        New-Item -Path $TrustedCatalogsKey -Force | Out-Null
    }
    $key = Join-Path $TrustedCatalogsKey $CatalogGuid
    if (-not (Test-Path -LiteralPath $key)) {
        New-Item -Path $key -Force | Out-Null
    }
    New-ItemProperty -Path $key -Name 'Id' -Value $CatalogGuid -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $key -Name 'Url' -Value $UncPath -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $key -Name 'Flags' -Value 1 -PropertyType DWord -Force | Out-Null
    Write-Host "Trusted catalog: $UncPath (Show in Menu)"
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
            $sub = Join-Path $DeveloperKey $addInId
            if (Test-Path -LiteralPath $sub) {
                Remove-Item -LiteralPath $sub -Recurse -Force
                $removed = $true
            }
        }
    }
    if (Test-Path $DeveloperKey) {
        if (Get-ItemProperty -Path $DeveloperKey -Name $ProdAddInId -ErrorAction SilentlyContinue) {
            Remove-ItemProperty -Path $DeveloperKey -Name $ProdAddInId -Force -ErrorAction SilentlyContinue
            $removed = $true
        }
        $prodSub = Join-Path $DeveloperKey $ProdAddInId
        if (Test-Path -LiteralPath $prodSub) {
            Remove-Item -LiteralPath $prodSub -Recurse -Force -ErrorAction SilentlyContinue
            $removed = $true
        }
    }
    Remove-TrustedCatalog
    if (Get-Command Remove-SmbShare -ErrorAction SilentlyContinue) {
        Remove-SmbShare -Name $ShareName -Force -ErrorAction SilentlyContinue
    }
    cmd.exe /c "net share $ShareName /delete >nul 2>nul"
    if (Test-Path -LiteralPath $InstallDir) {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force
        $removed = $true
        Write-Host "Removed $InstallDir"
    }
    Clear-MindGraphWefCache
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

Test-ManifestAppDomains $SourceManifest

Stop-WordForReload

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item -LiteralPath $SourceManifest -Destination $InstalledManifest -Force
Test-ManifestAppDomains $InstalledManifest

$AddInId = Get-AddInId $InstalledManifest
if ($AddInId -eq $DevSideloadId) {
    throw "This manifest is the localhost Dev Id. Use the downloaded production zip (Account → Word 加载项), not the git/Vite manifest.xml."
}

$manifestText = Get-Content -LiteralPath $InstalledManifest -Raw -Encoding UTF8
if ($manifestText -match 'https://localhost:3000') {
    throw "Manifest still points at https://localhost:3000 — production install requires hosted /word-addin/ URLs."
}

if (-not (Test-Path $DeveloperKey)) {
    New-Item -Path $DeveloperKey -Force | Out-Null
}

if (Get-ItemProperty -Path $DeveloperKey -Name $DevSideloadId -ErrorAction SilentlyContinue) {
    Remove-ItemProperty -Path $DeveloperKey -Name $DevSideloadId -Force
    Write-Host "Removed Dev sideload registry entry ($DevSideloadId)."
}
$devSub = Join-Path $DeveloperKey $DevSideloadId
if (Test-Path -LiteralPath $devSub) {
    Remove-Item -LiteralPath $devSub -Recurse -Force
}

$legacyProps = Get-ItemProperty -Path $DeveloperKey -ErrorAction SilentlyContinue
if ($legacyProps) {
    foreach ($name in $legacyProps.PSObject.Properties.Name) {
        if ($name -match '^(PS|RefreshAddins)') { continue }
        $val = [string]$legacyProps.$name
        if ($val -ne $InstalledManifest -and ($val -match 'src\\MindGraph\\word-addin\\manifest\.xml$' -or $val -match 'localhost:3000')) {
            Remove-ItemProperty -Path $DeveloperKey -Name $name -Force -ErrorAction SilentlyContinue
            Write-Host "Removed stale registry entry $name -> $val"
        }
    }
}

New-ItemProperty -Path $DeveloperKey -Name $AddInId -Value $InstalledManifest -PropertyType String -Force | Out-Null
New-ItemProperty -Path $DeveloperKey -Name 'RefreshAddins' -Value 1 -PropertyType DWord -Force | Out-Null

$verify = (Get-ItemProperty -Path $DeveloperKey -Name $AddInId).$AddInId
if ($verify -ne $InstalledManifest) {
    throw "Registry write failed for $AddInId"
}

Remove-HttpsWebsiteCatalogs
$unc = Ensure-CatalogShare $InstallDir
Register-TrustedCatalog $unc
Clear-MindGraphWefCache

Write-Host ""
Write-Host "Installed MindGraph for Word (Windows 10 / 11)."
Write-Host "Manifest: $InstalledManifest"
Write-Host "Developer registry: $verify"
if ($unc) {
    Write-Host "Shared folder catalog: $unc"
}
Write-Host ""
Write-Host "IMPORTANT — Custom tabs often need one manual Add:"
Write-Host "  1. Fully quit Word, then reopen and open a document"
Write-Host "  2. Home tab -> Add-ins (开始 -> 加载项)"
Write-Host "  3. More / Advanced -> SHARED FOLDER (共享文件夹) -> MindGraph -> Add"
Write-Host "     OR Upload My Add-in (上传我的加载项) and pick:"
Write-Host "        $InstalledManifest"
Write-Host "  4. Ribbon tab MindGraph should appear (not Acrobat / not MindGraph Dev)"
Write-Host "Do not run npm start for this install."
Write-Host ""

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
