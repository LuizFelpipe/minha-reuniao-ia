@echo off
title Assistente de Reunioes IA

cd /d "%~dp0"

echo [1/3] Verificando instalacao do Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado!
    echo Por favor, instale o Python (marque a opcao 'Add to PATH' na instalacao).
    echo Baixe em: python.org
    pause
    exit
)

echo [2/3] Verificando bibliotecas necessarias...
python -c "import streamlit; import google.generativeai" >nul 2>&1
if %errorlevel% neq 0 (
    echo Bibliotecas faltando. Instalando automaticamente...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao instalar bibliotecas. Verifique sua conexao com a internet.
        pause
        exit
    )
)

echo [3/3] Iniciando o sistema...
streamlit run reuniao_ia.py