@echo off
REM Gera um executavel standalone (Windows) do Downloader de Videos.
REM O .exe final fica em dist\DownloaderDeVideos.exe e nao precisa de Python
REM instalado na maquina que for rodar.
REM
REM Uso:
REM     pip install -r requirements.txt -r requirements-dev.txt
REM     build_exe.bat

python -m PyInstaller --onefile --windowed --name "DownloaderDeVideos" interface.py

echo.
echo Executavel gerado em: dist\DownloaderDeVideos.exe
