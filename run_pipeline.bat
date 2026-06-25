@echo off
cd /d "C:\warehouse-pipeline"
call venv\Scripts\activate
python run_service.py
