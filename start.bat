@echo off
:: Di chuyển vào đúng thư mục chứa code bot
cd /d %~dp0

:: Kích hoạt môi trường ảo
call .venv\Scripts\activate

:: Chạy server
python server.py

pause