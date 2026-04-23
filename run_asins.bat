@echo off
setlocal
REM Change to the directory of this script (handles spaces/Chinese paths)
pushd "%~dp0"

REM Activate venv if present
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
)

REM Ensure required packages are installed (silent)
python -m pip install -q --upgrade pip >nul 2>nul
pip show requests >nul 2>nul || pip install -q requests >nul 2>nul
pip show beautifulsoup4 >nul 2>nul || pip install -q beautifulsoup4 >nul 2>nul
pip show click >nul 2>nul || pip install -q click >nul 2>nul

REM Default parameters (edit if needed)
set "DOMAIN=https://www.amazon.com/"
set "INPUT=asins.txt"
set "OUTJSON=output.json"
set "OUTCSV=output.csv"

echo Running: python asins_export.py --domain %DOMAIN% --in "%INPUT%" --out-json "%OUTJSON%" --out-csv "%OUTCSV%"
python amazon_scraper_1.0.0.py --domain %DOMAIN% --in "%INPUT%" --out-json "%OUTJSON%" --out-csv "%OUTCSV%"

if %errorlevel% EQU 0 (
  echo.
  echo Success! Results saved to:
  echo   JSON: "%OUTJSON%"
  echo   CSV : "%OUTCSV%"
  if exist "%OUTCSV%" (
    for %%I in ("%OUTCSV%") do echo   CSV size: %%~zI bytes
  )
) else (
  echo.
  echo Failed. Please review the messages above for the error details.
)

echo.
echo Done. Press any key to exit.
pause >nul

popd
endlocal


