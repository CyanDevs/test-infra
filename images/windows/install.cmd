"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -ExecutionPolicy Unrestricted -NoLogo -NonInteractive -NoProfile -WindowStyle Hidden -File C:\scripts\install-windows-prereqs.ps1 -InstallPath C:\Downloads\prereqs\nuget -LaunchConfiguration SGX1FLC-NoIntelDrivers -DCAPClientType Azure"%1"
exit /B %ERRORLEVEL%
