# Run the Google i18n gap-fill CLI with Windows Node (VPN / system proxy).
# WSL cannot reach Google. Invoke from WSL:
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File \\wsl.localhost\...\frontend\i18n-google\run-on-windows-host.ps1 --locale=ta
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$node = 'C:\Program Files\nodejs\node.exe'
if (-not (Test-Path $node)) {
  $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
  if ($null -eq $nodeCmd) {
    throw 'Windows node.exe not found'
  }
  $node = $nodeCmd.Source
}
& $node (Join-Path $here 'cli.ts') @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
