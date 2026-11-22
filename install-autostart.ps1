# Start the gold dashboard server automatically when you sign in to Windows (no console window).
# Usage: gold\install-autostart.ps1            add the shortcut to the Startup folder
#        gold\install-autostart.ps1 -Remove    remove it
param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Gold Dashboard Server.lnk'
if ($Remove) {
  if (Test-Path $lnk) { Remove-Item $lnk; Write-Output "Removed $lnk" } else { Write-Output 'Not installed.' }
  exit 0
}
$pyw = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pyw)) { throw "Missing $pyw - create the venv first (see gold\README.md)." }
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($lnk)
$s.TargetPath = $pyw
$s.Arguments = '"' + (Join-Path $PSScriptRoot 'server.py') + '"'
$s.WorkingDirectory = $PSScriptRoot
$s.WindowStyle = 7  # minimized
$s.Description = 'Thai gold dashboard server (http://localhost:8765)'
$s.Save()
Write-Output "Installed: $lnk"
Write-Output 'The server starts at sign-in; log: gold\data\server.log'
