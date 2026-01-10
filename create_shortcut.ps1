$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("C:\Users\user\Desktop\Agent Terminal.lnk")
$Shortcut.TargetPath = "D:\code\agent-terminal\start.bat"
$Shortcut.WorkingDirectory = "D:\code\agent-terminal"
$Shortcut.Description = "Multi-Agent CLI Terminal"
$Shortcut.IconLocation = "C:\Windows\System32\cmd.exe,0"
$Shortcut.Save()
Write-Host "Shortcut created on Desktop!"
