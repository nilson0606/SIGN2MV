# Folder picker for the library location (Windows). Prints one JSON line:
#   {"path": "D:\\..."}  or  {"cancelled": true}
param([string]$InitialPath = "")
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.WindowState = "Minimized"
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "SIGN2MV"
$dialog.ShowNewFolderButton = $true
if ($InitialPath -and (Test-Path -LiteralPath $InitialPath)) { $dialog.SelectedPath = $InitialPath }
$result = $dialog.ShowDialog($owner)
$owner.Dispose()
if ($result -eq [System.Windows.Forms.DialogResult]::OK -and $dialog.SelectedPath) {
  @{ path = $dialog.SelectedPath } | ConvertTo-Json -Compress
} else {
  '{"cancelled":true}'
}
