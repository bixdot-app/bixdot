; BixDot NSIS Installer Hooks
; Kills any running BixDot processes before installation so the installer
; can overwrite bixdot-backend.exe without "file in use" errors.

!macro customInit
  ; Silently kill the backend and UI processes if running.
  ; /F = force, /T = include child processes, errors ignored (|| true equivalent).
  nsExec::Exec 'taskkill /F /T /IM bixdot-backend.exe'
  nsExec::Exec 'taskkill /F /T /IM BixDot.exe'
  ; Brief pause so the OS releases file handles before we write new files.
  Sleep 1500
!macroend

!macro customUnInstall
  ; Same cleanup on uninstall.
  nsExec::Exec 'taskkill /F /T /IM bixdot-backend.exe'
  nsExec::Exec 'taskkill /F /T /IM BixDot.exe'
  Sleep 1000
!macroend
