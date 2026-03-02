@echo off
title Importazione Automatica Foto
color 0E

echo ==========================================
echo   IMPORTAZIONE FOTO NEGLI ESERCIZI
echo ==========================================
echo.
echo   Assicurati che:
echo   1. Il file "importa_immagini.py" sia qui.
echo   2. Le foto siano nella cartella "nuove_foto".
echo.
pause

:: Questo comando dice a Python di eseguire lo script nella cartella corrente
python "importa_immagini.py"

echo.
echo ==========================================
echo   OPERAZIONE CONCLUSA
echo ==========================================
pause