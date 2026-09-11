@echo off
set CANDIDATES=%CANDIDATES%
if "%CANDIDATES%"=="" set CANDIDATES=30

set ROUTE_SECONDS=%ROUTE_SECONDS%
if "%ROUTE_SECONDS%"=="" set ROUTE_SECONDS=3

python scripts\run_final_benchmark.py --seed 42 --candidates %CANDIDATES% --route-seconds %ROUTE_SECONDS%
