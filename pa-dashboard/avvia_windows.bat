@echo off
echo ================================================
echo    PA Trasparenza - Dashboard Dipendenti Pubblici
echo ================================================
echo.

:: Verifica Python
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERRORE] Python non trovato. Scarica Python da https://python.org
    pause
    exit /b 1
)

:: Installa dipendenze
echo Installazione dipendenze...
pip install -r requirements.txt --quiet

echo.
echo Avvio dashboard su http://localhost:5050
echo Premi CTRL+C per fermare.
echo.

python app.py
pause



::# Copyright (C) 2026 osvaldo roscani
::# Questo file è parte di Chigi.
::# Licenza: GNU GPL v3 — vedi LICENSE per i dettagli.

