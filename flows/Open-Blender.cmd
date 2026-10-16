@echo off
set "BLUES_BLENDER=%~dp0.tools\blender\blender-4.5.9-windows-x64\blender.exe"
if not exist "%BLUES_BLENDER%" (
  echo Blender executable is missing from the project tools directory.
  pause
  exit /b 1
)
if exist "%~dp0renders\gp-animation\bakkuo-gp-animation.blend" (
  start "" "%BLUES_BLENDER%" "%~dp0renders\gp-animation\bakkuo-gp-animation.blend"
) else if exist "%~dp0renders\blender-duel-v2\bakkuo-ink-duel-v2.blend" (
  start "" "%BLUES_BLENDER%" "%~dp0renders\blender-duel-v2\bakkuo-ink-duel-v2.blend"
) else if exist "%~dp0renders\blender-duel\bakkuo-ink-duel.blend" (
  start "" "%BLUES_BLENDER%" "%~dp0renders\blender-duel\bakkuo-ink-duel.blend"
) else (
  start "" "%BLUES_BLENDER%"
)
