@echo off
REM Launcher for the Bioacoustics Rhythm Pipeline GUI (Windows).
REM Double-click this .bat file or create a shortcut to it on the Desktop.

setlocal

REM Locate project root (this script lives in GUI\)
set "GUI_DIR=%~dp0"
for %%I in ("%GUI_DIR%..") do set "PROJECT_DIR=%%~fI"

REM Try to find conda Python for rhythm_env
set "PYTHON_PATH="
set "ENV_ROOT="
for %%P in (
    "%USERPROFILE%\anaconda3\envs\rhythm_env\python.exe"
    "%USERPROFILE%\miniconda3\envs\rhythm_env\python.exe"
    "C:\ProgramData\anaconda3\envs\rhythm_env\python.exe"
    "%USERPROFILE%\AppData\Local\anaconda3\envs\rhythm_env\python.exe"
) do (
    if exist %%P (
        set "PYTHON_PATH=%%~P"
        for %%I in ("%%~dpP.") do set "ENV_ROOT=%%~fI"
        goto :found
    )
)

REM Fallback to python on PATH
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_PATH=python"
    goto :found
)
echo ERROR: Could not find Python. Install Anaconda or add Python to PATH.
pause
exit /b 1

:found
if defined ENV_ROOT (
    set "PATH=%ENV_ROOT%;%ENV_ROOT%\Library\mingw-w64\bin;%ENV_ROOT%\Library\usr\bin;%ENV_ROOT%\Library\bin;%ENV_ROOT%\Scripts;%ENV_ROOT%\bin;%PATH%"
    set "CONDA_PREFIX=%ENV_ROOT%"
    set "CONDA_DEFAULT_ENV=rhythm_env"
)
cd /d "%PROJECT_DIR%"
"%PYTHON_PATH%" "%GUI_DIR%pipeline_gui.py"
if %errorlevel% neq 0 pause
