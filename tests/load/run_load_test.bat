@echo off
REM Helios Load Test Runner for Windows
REM Validates throughput, latency, and reliability claims

setlocal enabledelayedexpansion

REM Default configuration
if "%HOST%"=="" set HOST=localhost
if "%PORT%"=="" set PORT=8080
if "%THREADS%"=="" set THREADS=100
if "%DURATION%"=="" set DURATION=600
if "%RAMPUP%"=="" set RAMPUP=60
if "%THROUGHPUT%"=="" set THROUGHPUT=50000

REM Create results directory
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/: " %%a in ('time /t') do (set mytime=%%a%%b)
set TIMESTAMP=%mydate%_%mytime%
set RESULTS_DIR=results\%TIMESTAMP%
mkdir "%RESULTS_DIR%" 2>nul

echo ======================================
echo Helios Ingestion Load Test
echo ======================================
echo.
echo Configuration:
echo   Target: http://%HOST%:%PORT%
echo   Threads: %THREADS%
echo   Duration: %DURATION%s
echo   Ramp-up: %RAMPUP%s
echo   Target Throughput: %THROUGHPUT% events/sec
echo.
echo Results will be saved to: %RESULTS_DIR%
echo.

REM Check if JMeter is installed
where jmeter >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: JMeter is not installed or not in PATH
    echo Please install JMeter: https://jmeter.apache.org/download_jmeter.cgi
    echo Add JMeter bin directory to PATH
    exit /b 1
)

echo Starting load test...
echo.

REM Run JMeter in non-GUI mode
jmeter -n ^
  -t ingestion_load_test.jmx ^
  -Jhost=%HOST% ^
  -Jport=%PORT% ^
  -Jthreads=%THREADS% ^
  -Jduration=%DURATION% ^
  -Jrampup=%RAMPUP% ^
  -Jthroughput=%THROUGHPUT% ^
  -l "%RESULTS_DIR%\results.jtl" ^
  -j "%RESULTS_DIR%\jmeter.log" ^
  -e -o "%RESULTS_DIR%\html-report"

echo.
echo ======================================
echo Load Test Complete!
echo ======================================
echo.
echo Results:
echo   JTL File: %RESULTS_DIR%\results.jtl
echo   HTML Report: %RESULTS_DIR%\html-report\index.html
echo   Log File: %RESULTS_DIR%\jmeter.log
echo.
echo Open HTML report in browser:
echo   file:///%CD%\%RESULTS_DIR%\html-report\index.html
echo.

pause
