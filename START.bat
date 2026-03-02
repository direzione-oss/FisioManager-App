@echo off
title FisioManager Pro - Centro Medico For Me
color 3F
cls

echo ========================================================
echo      AVVIO DI FISIOMANAGER PRO - PORTA 8502
echo ========================================================
echo.
echo  [1] Il server sta partendo...
echo.
echo  --------------------------------------------------------
echo  COME ACCEDERE AL PROGRAMMA:
echo  --------------------------------------------------------
echo.
echo  1. DA QUESTO COMPUTER:
echo     Apri Chrome/Edge e vai su:  http://localhost:8502
echo.
echo  2. DA UN ALTRO PC O TABLET (stesso Wi-Fi):
echo     Devi usare il Tuo Indirizzo IP locale.
echo     Il tuo IP e':
ipconfig | findstr /i "ipv4"
echo     Quindi sul tablet scriverai: http://[IL_TUO_NUMERO]:8502
echo.
echo ========================================================
echo  NON CHIUDERE QUESTA FINESTRA NERA
echo ========================================================
echo.

:: Avvia Streamlit sulla porta 8502, accessibile da rete (0.0.0.0)
:: --browser.serverAddress=localhost forza l'apertura corretta su questo PC
python -m streamlit run app.py --server.address=0.0.0.0 --server.port=8502 --browser.serverAddress=localhost

pause