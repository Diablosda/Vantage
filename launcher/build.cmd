@echo off
setlocal
pushd "%~dp0.."
"%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /reference:System.Windows.Forms.dll /win32icon:web\assets\vantage.ico /out:Vantage.exe launcher\Program.cs
if errorlevel 1 goto build_failed
"%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /reference:System.Windows.Forms.dll /reference:System.Web.Extensions.dll /win32icon:web\assets\vantage.ico /out:Vantage.Dialogs.exe launcher\Dialogs.cs
:build_failed
set "VANTAGE_BUILD_RESULT=%ERRORLEVEL%"
popd
exit /b %VANTAGE_BUILD_RESULT%
