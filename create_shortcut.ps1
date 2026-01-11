$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$Shortcut = $WshShell.CreateShortcut("$DesktopPath\Agent Terminal.lnk")
$Shortcut.TargetPath = "$ScriptDir\start.bat"
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Description = "Multi-Agent CLI Terminal"
$Shortcut.IconLocation = "C:\Windows\System32\cmd.exe,0"
$Shortcut.Save()

Write-Host "Shortcut created: $DesktopPath\Agent Terminal.lnk"
Write-Host "Target: $ScriptDir\start.bat"
