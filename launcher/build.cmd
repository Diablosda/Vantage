@echo off
setlocal
pushd "%~dp0.."
"%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /reference:System.Windows.Forms.dll /win32icon:web\assets\vantage.ico /out:Vantage.exe launcher\Program.cs
set "VANTAGE_BUILD_RESULT=%ERRORLEVEL%"
popd
exit /b %VANTAGE_BUILD_RESULT%
