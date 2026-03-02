@echo off
title Installazione Dipendenze FisioManager
color 0A

echo ========================================================
echo   INSTALLAZIONE LIBRERIE PER FISIOMANAGER PRO
echo ========================================================
echo.
echo   Assicurati di aver installato Python prima di procedere.
echo   Sto per installare: streamlit, pandas, fpdf, altair...
echo.
pause

echo.
echo   [1/4] Aggiornamento di PIP...
python -m pip install --upgrade pip

echo.
echo   [2/4] Installazione Streamlit e Pandas...
pip install streamlit pandas

echo.
echo   [3/4] Installazione Generatore PDF (FPDF)...
pip install fpdf

echo.
echo   [4/4] Installazione Grafici (Altair)...
pip install altair

echo.
echo ========================================================
echo   INSTALLAZIONE COMPLETATA!
echo   Ora puoi usare il file "Avvia_FisioManager.bat"
echo ========================================================
echo.
pause