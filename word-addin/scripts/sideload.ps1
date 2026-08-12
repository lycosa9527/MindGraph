# Register / unregister MindGraph Word add-in via Office WEF Developer registry.
# Replaces office-addin-debugging (avoids deprecated Microsoft Teams toolkit tree).
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('start', 'stop')]
    [string]$Action
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ManifestPath = (Resolve-Path (Join-Path $Root 'manifest.xml')).Path

function Get-AddInId {
    [xml]$xml = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8
    $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
    $ns.AddNamespace('o', 'http://schemas.microsoft.com/office/appforoffice/1.1')
    $idNode = $xml.SelectSingleNode('//o:Id', $ns)
    if (-not $idNode -or [string]::IsNullOrWhiteSpace($idNode.InnerText)) {
        throw "Could not read <Id> from $ManifestPath"
    }
    return $idNode.InnerText.Trim()
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

    $appPaths = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Winword.exe',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\Winword.exe'
    )
    foreach ($key in $appPaths) {
        if (Test-Path $key) {
            $default = (Get-ItemProperty -Path $key).'(default)'
            if ($default -and (Test-Path -LiteralPath $default)) {
                return $default
            }
        }
    }

    return $null
}

$DeveloperKey = 'HKCU:\SOFTWARE\Microsoft\Office\16.0\Wef\Developer'
$AddInId = Get-AddInId

if (-not (Test-Path $DeveloperKey)) {
    New-Item -Path $DeveloperKey -Force | Out-Null
}

switch ($Action) {
    'start' {
        New-ItemProperty -Path $DeveloperKey -Name $AddInId -Value $ManifestPath -PropertyType String -Force | Out-Null
        Write-Host "Registered add-in $AddInId"
        Write-Host "Manifest: $ManifestPath"
        Write-Host "1) Run 'npm run dev' in another terminal (if not already)."
        Write-Host "2) In Word: Insert > Add-ins > Developer Add-ins > MindGraph."

        $wordExe = Find-WinWord
        if ($wordExe) {
            Write-Host "Opening Word: $wordExe"
            Start-Process -FilePath $wordExe
        } else {
            Write-Host "Could not find WINWORD.EXE; open Word manually, then use Insert > Add-ins > Developer Add-ins."
        }
    }
    'stop' {
        if (Get-ItemProperty -Path $DeveloperKey -Name $AddInId -ErrorAction SilentlyContinue) {
            Remove-ItemProperty -Path $DeveloperKey -Name $AddInId -Force
            Write-Host "Unregistered add-in $AddInId"
        } else {
            Write-Host "Add-in $AddInId was not registered."
        }
    }
}
