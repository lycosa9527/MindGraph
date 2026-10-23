# Translate chrome-extension message catalogs with Windows Node (VPN / system proxy).
# WSL cannot reach Google. Invoke from WSL:
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File \\wsl.localhost\...\frontend\i18n-google\translate-extension-on-host.ps1
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$node = 'C:\Program Files\nodejs\node.exe'
if (-not (Test-Path $node)) {
  $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
  if ($null -ne $nodeCmd) {
    $node = $nodeCmd.Source
  } else {
    $cursorNode = Join-Path $env:LOCALAPPDATA 'Programs\cursor\resources\app\resources\helpers\node.exe'
    if (Test-Path $cursorNode) {
      $node = $cursorNode
    } else {
      throw 'Windows node.exe not found'
    }
  }
}
& $node (Join-Path $here 'translate-extension-messages.mjs') @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
