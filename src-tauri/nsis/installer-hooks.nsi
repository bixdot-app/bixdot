; BixDot NSIS Installer Hooks
;
; IMPORTANT: Tauri v2's NSIS template only invokes macros named
; NSIS_HOOK_PREINSTALL / NSIS_HOOK_POSTINSTALL / NSIS_HOOK_PREUNINSTALL /
; NSIS_HOOK_POSTUNINSTALL. The previous names (customInit/customUnInstall)
; are electron-builder's convention and were NEVER executed — which let
; upgrades run while bixdot-backend.exe was still alive, fail to replace
; the locked binaries, and leave a half-upgraded install (v0.5/v0.6 mix).

!macro NSIS_HOOK_PREINSTALL
  ; Kill the UI and the backend sidecar (and their child processes) so
  ; every file can be replaced. /F force, /T child tree, errors ignored.
  nsExec::Exec 'taskkill /F /T /IM bixdot.exe'
  nsExec::Exec 'taskkill /F /T /IM bixdot-backend.exe'
  ; Let the OS release file handles before touching files.
  Sleep 1500
  ; Purge stale app files from any previous version so no old binary or
  ; resource can survive an upgrade. User data is NOT here — it lives in
  ; ~/.bixdot and is never touched by the installer.
  Delete "$INSTDIR\bixdot.exe"
  Delete "$INSTDIR\bixdot-backend.exe"
  RMDir /r "$INSTDIR\_up_"
  Sleep 500
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  ; Same cleanup on uninstall — nothing may hold the files.
  nsExec::Exec 'taskkill /F /T /IM bixdot.exe'
  nsExec::Exec 'taskkill /F /T /IM bixdot-backend.exe'
  Sleep 1000
!macroend
