@echo off
chcp 65001 >nul 2>&1
setlocal

echo ============================================================
echo   compta-ecom — Automatisation comptable e-commerce
echo ============================================================
echo.

REM -- Verifier que le dossier CSV contient au moins un .csv -----
set "CSV_DIR=%~dp01_DEPOSER_CSV_ICI"
set "FOUND_CSV=0"
for %%f in ("%CSV_DIR%\*.csv") do set "FOUND_CSV=1"

if "%FOUND_CSV%"=="0" (
    echo   ERREUR : Aucun fichier CSV trouve.
    echo.
    echo   Deposez vos fichiers dans le dossier :
    echo     1_DEPOSER_CSV_ICI
    echo   puis relancez ce script.
    echo.
    pause
    exit /b 1
)

REM -- Construire le nom du fichier de sortie avec la date -------
set "YYYY=%date:~6,4%"
set "MM=%date:~3,2%"
set "DD=%date:~0,2%"
REM Fallback via wmic si le format date locale est different
if "%YYYY%"=="" for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set "DT=%%a"
if defined DT (
    set "YYYY=%DT:~0,4%"
    set "MM=%DT:~4,2%"
    set "DD=%DT:~6,2%"
)

set "OUTPUT_FILE=2_RESULTATS\ecritures_%YYYY%-%MM%-%DD%.xlsx"

REM -- Lancer le pipeline ----------------------------------------
echo   Traitement en cours...
echo.

"%~dp0compta-ecom.exe" "%CSV_DIR%" "%~dp0%OUTPUT_FILE%" --config-dir "%~dp0config"

if errorlevel 1 (
    echo.
    echo   ERREUR : Le traitement a echoue. Consultez les messages ci-dessus.
    echo.
    pause
    exit /b 1
)

echo.
echo   Fichier genere : %OUTPUT_FILE%
echo.

REM -- Ouvrir le fichier Excel automatiquement -------------------
start "" "%~dp0%OUTPUT_FILE%"

echo   Le fichier Excel s'ouvre automatiquement.
echo.
pause
