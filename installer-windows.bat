@echo off
chcp 65001 >nul
title Installation compta-ecom
echo.
echo ============================================
echo   Installation de compta-ecom
echo   Outil de comptabilite e-commerce
echo ============================================
echo.

:: -------------------------------------------
:: 1. Verification de Git
:: -------------------------------------------
where git >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] Git n'est pas installe sur cette machine.
    echo.
    echo     Veuillez installer Git depuis :
    echo     https://git-scm.com/download/win
    echo.
    echo     Lancez l'installeur, gardez les options par defaut,
    echo     puis relancez ce script.
    echo.
    pause
    exit /b 1
)
echo [OK] Git detecte.

:: -------------------------------------------
:: 2. Verification de Python 3.11+
:: -------------------------------------------
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] Python n'est pas installe sur cette machine.
    echo.
    echo     Veuillez installer Python depuis :
    echo     https://www.python.org/downloads/
    echo.
    echo     IMPORTANT : Cochez la case "Add Python to PATH"
    echo     lors de l'installation !
    echo.
    echo     Puis relancez ce script.
    echo.
    pause
    exit /b 1
)

:: Verifier la version de Python (3.11 minimum)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)
if %PYMAJOR% LSS 3 (
    echo [!] Python %PYVER% detecte, mais la version 3.11+ est requise.
    echo     Veuillez mettre a jour Python : https://www.python.org/downloads/
    pause
    exit /b 1
)
if %PYMAJOR%==3 if %PYMINOR% LSS 11 (
    echo [!] Python %PYVER% detecte, mais la version 3.11+ est requise.
    echo     Veuillez mettre a jour Python : https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python %PYVER% detecte.

:: -------------------------------------------
:: 3. Cloner le depot
:: -------------------------------------------
echo.
echo Telechargement de compta-ecom...

if exist "%USERPROFILE%\compta-ecom" (
    echo [!] Le dossier %USERPROFILE%\compta-ecom existe deja.
    echo     Mise a jour du code...
    cd /d "%USERPROFILE%\compta-ecom"
    git pull
) else (
    git clone https://github.com/pyn9tw49hq-star/compta-ecom.git "%USERPROFILE%\compta-ecom"
    cd /d "%USERPROFILE%\compta-ecom"
)

if %ERRORLEVEL% NEQ 0 (
    echo [!] Erreur lors du telechargement. Verifiez votre connexion internet.
    pause
    exit /b 1
)
echo [OK] Code telecharge.

:: -------------------------------------------
:: 4. Installer l'outil
:: -------------------------------------------
echo.
echo Installation des dependances...
pip install -e . >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Erreur lors de l'installation. Essai avec pip3...
    pip3 install -e . >nul 2>&1
)
if %ERRORLEVEL% NEQ 0 (
    echo [!] L'installation a echoue. Contactez l'administrateur.
    pause
    exit /b 1
)
echo [OK] compta-ecom installe.

:: -------------------------------------------
:: 5. Verification
:: -------------------------------------------
echo.
compta-ecom --help >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ============================================
    echo   Installation terminee avec succes !
    echo ============================================
    echo.
    echo   Utilisation :
    echo   compta-ecom chemin\vers\csv\ sortie.xlsx
    echo.
    echo   Guide utilisateur :
    echo   %USERPROFILE%\compta-ecom\docs\guide-utilisateur.md
    echo.
    echo   Configuration :
    echo   %USERPROFILE%\compta-ecom\config\
    echo.
) else (
    echo [!] L'installation semble avoir reussi mais la commande
    echo     compta-ecom n'est pas reconnue. Fermez ce terminal,
    echo     ouvrez-en un nouveau, et tapez : compta-ecom --help
)

pause
