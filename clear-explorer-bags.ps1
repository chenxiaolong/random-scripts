if (([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')) {
    throw "Don't run this script as an Administrator"
}

# Stop-Process doesn't allow setting the exit code for Win32's TerminateProcess(), so:
#
#     Get-Process -name explorer | Stop-Process
#
# just makes explorer.exe restart.
taskkill /f /im explorer.exe

Remove-Item -recurse -path `
    "HKCU:Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\BagMRU", `
    "HKCU:Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags", `
    "HKCU:Software\Microsoft\Windows\Shell\BagMRU", `
    "HKCU:Software\Microsoft\Windows\Shell\Bags"

explorer.exe