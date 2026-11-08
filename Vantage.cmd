@echo off
set "PREVIS_ROOT=%~dp0"
powershell -NoProfile -Command "$taskRoot=$env:PREVIS_ROOT; $taskPython=Join-Path $taskRoot '..\blender\blender-5.2.2-windows-x64\5.2\python\bin\python.exe'; Start-Process -FilePath $taskPython -ArgumentList '-m','server','--open' -WorkingDirectory $taskRoot -WindowStyle Hidden"
