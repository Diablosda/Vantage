Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"
Var TestMode
!ifndef VERSION
!error "VERSION required"
!endif
Name "Vantage ${VERSION}"
VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=1033 "ProductName" "Vantage"
VIAddVersionKey /LANG=1033 "FileDescription" "Vantage Offline Installer"
VIAddVersionKey /LANG=1033 "FileVersion" "${VERSION}.0"
Icon "${STAGE}\web\assets\vantage.ico"
UninstallIcon "${STAGE}\web\assets\vantage.ico"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\Vantage"
InstallDirRegKey HKCU "Software\Vantage" "InstallDir"
RequestExecutionLevel user
SetCompressor zlib
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"
Function .onInit
 ${GetParameters} $R0
 ${GetOptions} $R0 "/TEST=" $TestMode
 ${IfNot} ${RunningX64}
  MessageBox MB_ICONSTOP "Vantage requires Windows x64."
  Abort
 ${EndIf}
FunctionEnd
Section "Vantage" SEC_MAIN
 IfFileExists "$INSTDIR\.vantage-installation" 0 stopped
 ExecWait '"$INSTDIR\Vantage.exe" --stop' $0
 IntCmp $0 0 stopped
 MessageBox MB_ICONSTOP "Vantage has active work. Finish or cancel it before updating."
 Abort
 stopped:
 SetOutPath "$INSTDIR"
 File /r "${STAGE}\*"
 WriteUninstaller "$INSTDIR\Uninstall.exe"
 StrCmp $TestMode "1" test_install
 WriteRegStr HKCU "Software\Vantage" "InstallDir" "$INSTDIR"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Vantage" "DisplayName" "Vantage"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Vantage" "DisplayVersion" "${VERSION}"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Vantage" "UninstallString" '"$INSTDIR\Uninstall.exe"'
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Vantage" "NoModify" 1
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Vantage" "NoRepair" 1
 CreateDirectory "$SMPROGRAMS\Vantage"
 CreateShortCut "$SMPROGRAMS\Vantage\Vantage.lnk" "$INSTDIR\Vantage.exe"
 CreateShortCut "$SMPROGRAMS\Vantage\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
 CreateShortCut "$DESKTOP\Vantage.lnk" "$INSTDIR\Vantage.exe"
 Goto installed
 test_install:
 FileOpen $0 "$INSTDIR\.test-installation" w
 FileWrite $0 "Test installation"
 FileClose $0
 installed:
SectionEnd
Section "Uninstall"
 ; Delete only the manifest of files we installed. Never recursively delete user files.
 ExecWait '"$INSTDIR\Vantage.exe" --stop' $0
 IntCmp $0 0 stopped
 MessageBox MB_ICONSTOP "Vantage has active work. Finish or cancel it before uninstalling."
 Abort
 stopped:
 IfFileExists "$INSTDIR\Vantage.exe" 0 done
 IfFileExists "$INSTDIR\server.py" 0 done
 IfFileExists "$INSTDIR\.test-installation" remove_files
 Delete "$DESKTOP\Vantage.lnk"
 Delete "$SMPROGRAMS\Vantage\Vantage.lnk"
 Delete "$SMPROGRAMS\Vantage\Uninstall.lnk"
 RMDir "$SMPROGRAMS\Vantage"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Vantage"
 DeleteRegKey HKCU "Software\Vantage"
 remove_files:
 Delete "$INSTDIR\.test-installation"
 !include "${UNINSTALL_LIST}"
 Delete "$INSTDIR\Uninstall.exe"
 RMDir "$INSTDIR"
 done:
SectionEnd
