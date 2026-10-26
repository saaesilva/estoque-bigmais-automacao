@echo off
chcp 65001 > nul
title Coletor de Estoque Big Mais - Desktop

cd /d "%~dp0"

:: Localiza o executável do Python (prioriza a venv do projeto)
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

:MENU
cls
echo ===================================================================
echo             COLETA DE ESTOQUE BIG MAIS - DESKTOP
echo ===================================================================
echo.
echo   [1] Coleta COMPLETA em segundo plano (Headless) + Enviar ao GitHub
echo   [2] Coleta COMPLETA com navegador VISIVEL na tela + Enviar ao GitHub
echo   [3] Teste RAPIDO (Apenas 5 produtos na tela) + Enviar ao GitHub
echo   [4] Apenas Enviar o arquivo estoque_bigmais.db atual para o GitHub
echo   [5] Sair
echo.
echo ===================================================================
set /p OPCAO="Escolha uma opcao (1-5): "

if "%OPCAO%"=="1" goto OP1
if "%OPCAO%"=="2" goto OP2
if "%OPCAO%"=="3" goto OP3
if "%OPCAO%"=="4" goto OP4
if "%OPCAO%"=="5" goto FIM
echo.
echo Opcao invalida! Pressione qualquer tecla para tentar novamente.
pause > nul
goto MENU

:OP1
echo.
echo Iniciando coleta completa em segundo plano...
%PY% rodar_desktop.py
goto FINALIZAR

:OP2
echo.
echo Iniciando coleta completa com navegador visivel...
%PY% rodar_desktop.py --visivel
goto FINALIZAR

:OP3
echo.
echo Iniciando teste rapido com 5 produtos...
%PY% rodar_desktop.py --visivel --limite 5
goto FINALIZAR

:OP4
echo.
echo Exportando catalogo JSON e enviando arquivos para o GitHub...
%PY% -c "from rodar_desktop import upload_db_to_github, exportar_json, GITHUB_TOKEN, REPO, CAMINHO_DB, CAMINHO_JSON; exportar_json(CAMINHO_DB, CAMINHO_JSON); upload_db_to_github(GITHUB_TOKEN, REPO, CAMINHO_DB, 'estoque_bigmais.db'); upload_db_to_github(GITHUB_TOKEN, REPO, CAMINHO_JSON, 'estoque_bigmais.json')"
goto FINALIZAR

:FINALIZAR
echo.
echo ===================================================================
echo Processo concluido!
echo Pressione qualquer tecla para voltar ao menu...
pause > nul
goto MENU

:FIM
exit
