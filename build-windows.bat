@echo off
REM BaixaFacil - Build script para Windows (.exe)
REM Execute este script em um PC com Windows

echo [1/4] Criando ambiente virtual...
python -m venv venv-win
call venv-win\Scripts\activate.bat

echo [2/4] Instalando dependencias...
pip install customtkinter yt-dlp pyinstaller

echo [3/4] Gerando executavel...
for /f "tokens=*" %%i in ('python -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i
for /f "tokens=*" %%i in ('where yt-dlp') do set YTDLP_PATH=%%i

pyinstaller --onedir --windowed ^
  --name "BaixaFacil" ^
  --add-binary "%YTDLP_PATH%;." ^
  --add-data "%CTK_PATH%;customtkinter" ^
  --hidden-import customtkinter ^
  --noconfirm ^
  main.py

echo [4/4] Pronto! O executavel esta em: dist\BaixaFacil\BaixaFacil.exe
pause
