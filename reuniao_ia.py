import os
import time
import subprocess
import re
import shutil
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def listar_dispositivos_audio(ffmpeg_path):
    """Lista os dispositivos de áudio disponíveis no sistema usando ffmpeg."""
    if not ffmpeg_path:
        return []
        
    try:
        # Executa o comando para listar dispositivos
        cmd = [ffmpeg_path, '-list_devices', 'true', '-f', 'dshow', '-i', 'dummy']
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        output = result.stderr
        
        devices = []
        capturing = False
        
        for line in output.split('\n'):
            if "DirectShow audio devices" in line:
                capturing = True
                continue
            if "DirectShow video devices" in line:
                capturing = False
                continue
            
            if capturing:
                if "Alternative name" in line: continue
                match = re.search(r'"([^"]+)"', line)
                if match:
                    devices.append(match.group(1))
        return devices
    except Exception:
        return []

def gerar_ata_com_gemini(audio_path, api_key, model_name):
    """Envia o áudio para o Gemini e retorna a ata formatada."""
    genai.configure(api_key=api_key)
    
    # Upload do arquivo
    audio_file = genai.upload_file(path=audio_path)
    
    # Aguarda processamento do áudio pelo Google
    while audio_file.state.name == "PROCESSING":
        time.sleep(2)
        audio_file = genai.get_file(audio_file.name)

    if audio_file.state.name == "FAILED":
        raise ValueError("Falha no processamento do áudio pelo Gemini.")

    model = genai.GenerativeModel(model_name)

    prompt = """
    Você é um secretário executivo experiente e eficiente.
    Ouça o áudio desta reunião com atenção.
    
    Sua tarefa é gerar um documento estruturado contendo:
    1. **Resumo Executivo**: Um parágrafo conciso.
    2. **Participantes**: Identifique pelo contexto ou liste genérico.
    3. **Pontos Principais**: Lista de tópicos.
    4. **Ações (Action Items)**: Quem faz o quê.
    5. **Decisões**: O que foi decidido.
    
    O tom deve ser profissional e corporativo. Responda em Português do Brasil.
    """

    response = model.generate_content([prompt, audio_file])
    return response.text

def main():
    # --- CONFIGURAÇÃO INICIAL ---
    st.set_page_config(page_title="Assistente de Reunião IA", page_icon="🎙️")
    
    # Detecção do FFmpeg (Compatível com Windows Local e Cloud/Linux)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_local_win = os.path.join(script_dir, "ffmpeg.exe")
    ffmpeg_path = None

    if shutil.which("ffmpeg"):
        ffmpeg_path = "ffmpeg" # Instalado no sistema (Cloud/Linux)
    elif os.path.exists(ffmpeg_local_win):
        ffmpeg_path = ffmpeg_local_win # Local Windows

    # --- INTERFACE ---
    st.title("🎙️ Assistente de Reunião com IA")
    
    # Sidebar de Configuração
    with st.sidebar:
        st.header("Configurações")
        api_key = st.text_input("Chave API Google (Gemini)", value=os.getenv("GOOGLE_API_KEY") or "", type="password")
        
        model_options = ["gemini-1.5-flash", "gemini-1.5-pro"]
        model_name = st.selectbox("Modelo IA", model_options, index=0)
        
        st.markdown("---")
        st.markdown("Desenvolvido para reuniões Teams/Meet.")

    if not api_key:
        st.warning("⚠️ Por favor, insira sua Chave de API do Google na barra lateral para continuar.")
        st.stop()

    # Pasta de gravações
    pasta_gravacoes = os.path.join(script_dir, "gravacoes")
    if not os.path.exists(pasta_gravacoes):
        os.makedirs(pasta_gravacoes)

    # --- ESTADO DA SESSÃO ---
    if 'gravando' not in st.session_state:
        st.session_state.gravando = False
    if 'processo_gravacao' not in st.session_state:
        st.session_state.processo_gravacao = None
    if 'arquivo_atual' not in st.session_state:
        st.session_state.arquivo_atual = None
    if 'auto_processar' not in st.session_state:
        st.session_state.auto_processar = False

    # --- LÓGICA PRINCIPAL ---
    
    # Variáveis para processamento posterior
    audio_bytes = None
    file_suffix = ".mp3"

    # MODO GRAVAÇÃO (Bloqueia a tela para focar no Stop)
    if st.session_state.gravando:
        st.error(f"🔴 GRAVANDO... ({st.session_state.arquivo_atual})")
        st.info("Minimize esta janela e vá para sua reunião. Não feche o navegador.")
        
        # Botão de Parar
        if st.button("⏹️ Parar Gravação e Gerar Ata", type="primary"):
            proc = st.session_state.processo_gravacao
            if proc:
                try:
                    proc.communicate(input=b'q', timeout=5)
                except:
                    proc.terminate()
            
            st.session_state.gravando = False
            st.session_state.processo_gravacao = None
            st.session_state.auto_processar = True # Ativa gatilho para processar na recarga
            st.rerun()

    # MODO NORMAL (Abas de seleção)
    else:
        tab_nova, tab_existente, tab_upload = st.tabs(["🔴 Nova Gravação", "📂 Gravações Antigas", "📤 Upload Manual"])
        
        # ABA 1: NOVA GRAVAÇÃO
        with tab_nova:
            st.markdown("### Gravar Áudio do Sistema (Teams/Meet)")
            
            # Verifica se está no Windows Local (único lugar onde dshow funciona)
            if os.name == 'nt' and ffmpeg_path:
                dispositivos = listar_dispositivos_audio(ffmpeg_path)
                
                if dispositivos:
                    # Tenta selecionar Mixagem Estéreo automaticamente
                    idx_padrao = 0
                    for i, dev in enumerate(dispositivos):
                        if "mixagem" in dev.lower() or "stereo" in dev.lower():
                            idx_padrao = i
                            break
                    
                    device_selecionado = st.selectbox("Fonte de Áudio:", dispositivos, index=idx_padrao)
                    
                    if st.button("Iniciar Gravação"):
                        nome_arquivo = time.strftime("reuniao_%Y-%m-%d_%H-%M-%S.mp3")
                        caminho_completo = os.path.join(pasta_gravacoes, nome_arquivo)
                        
                        cmd = [
                            ffmpeg_path, '-y', '-f', 'dshow', 
                            '-i', f'audio={device_selecionado}', 
                            '-vn', caminho_completo
                        ]
                        
                        try:
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, startupinfo=startupinfo)
                            
                            st.session_state.processo_gravacao = proc
                            st.session_state.gravando = True
                            st.session_state.arquivo_atual = nome_arquivo
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao iniciar gravação: {e}")
                else:
                    st.warning("Nenhum dispositivo de áudio encontrado. Verifique se o microfone/mixagem estéreo está habilitado.")
            else:
                st.info("ℹ️ A gravação direta do sistema requer Windows e FFmpeg local.")
                st.warning("Se você estiver na Nuvem (Streamlit Cloud), use a aba 'Upload Manual'.")

                # Diagnóstico para ajudar a identificar o problema
                st.markdown("---")
                st.caption("🔍 Diagnóstico Técnico:")
                st.text(f"Sistema Operacional: {os.name} (Esperado: nt)")
                st.text(f"Arquivo local esperado: {ffmpeg_local_win}")
                st.text(f"Status do arquivo: {'❌ Não encontrado' if not os.path.exists(ffmpeg_local_win) else '✅ Encontrado'}")

        # ABA 2: GRAVAÇÕES ANTIGAS
        with tab_existente:
            st.markdown("### Histórico de Gravações")
            arquivos = [f for f in os.listdir(pasta_gravacoes) if f.endswith(('.mp3', '.wav', '.m4a'))]
            
            # Ordena por data de modificação (mais recente primeiro)
            arquivos.sort(key=lambda x: os.path.getmtime(os.path.join(pasta_gravacoes, x)), reverse=True)
            
            if arquivos:
                # Se acabou de gravar, seleciona o arquivo atual
                idx_selecao = 0
                if st.session_state.auto_processar and st.session_state.arquivo_atual in arquivos:
                    idx_selecao = arquivos.index(st.session_state.arquivo_atual)
                
                arquivo_selecionado = st.selectbox("Selecione a gravação:", arquivos, index=idx_selecao)
                
                if arquivo_selecionado:
                    caminho_arquivo = os.path.join(pasta_gravacoes, arquivo_selecionado)
                    st.audio(caminho_arquivo)
                    
                    # Prepara para processamento
                    with open(caminho_arquivo, "rb") as f:
                        audio_bytes = f.read()
                    file_suffix = os.path.splitext(arquivo_selecionado)[1]
            else:
                st.info("Nenhuma gravação encontrada.")
                if st.button("🔄 Atualizar"):
                    st.rerun()

        # ABA 3: UPLOAD
        with tab_upload:
            st.markdown("### Upload de Arquivo")
            uploaded_file = st.file_uploader("Arraste seu arquivo aqui", type=["mp3", "wav", "m4a", "webm", "mp4"])
            
            if uploaded_file:
                audio_bytes = uploaded_file.getvalue()
                file_suffix = os.path.splitext(uploaded_file.name)[1]
                st.audio(audio_bytes, format=uploaded_file.type if "audio" in uploaded_file.type else "video/webm")

    # --- PROCESSAMENTO DA IA ---
    st.markdown("---")
    st.subheader("2. Gerar Ata e Resumo")

    # Botão de ação (Manual ou Automático)
    pode_processar = audio_bytes is not None
    gatilho_auto = st.session_state.auto_processar and pode_processar
    
    if gatilho_auto:
        st.info("🚀 Iniciando processamento automático da gravação finalizada...")

    if st.button("✨ Gerar Ata com IA", disabled=not pode_processar, type="primary") or gatilho_auto:
        with st.spinner("A IA está ouvindo o áudio e escrevendo a ata..."):
            try:
                # Salva temporário
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
                    tmp_file.write(audio_bytes)
                    tmp_filename = tmp_file.name
                
                # Chama Gemini
                resultado = gerar_ata_com_gemini(tmp_filename, api_key, model_name)
                
                # Exibe Resultado
                st.success("Ata gerada com sucesso!")
                st.markdown(resultado)
                
                # Download
                st.download_button("📥 Baixar Ata (.txt)", data=resultado, file_name="ata_reuniao.txt")
                
                # Limpeza
                os.unlink(tmp_filename)
                st.session_state.auto_processar = False # Reseta gatilho
                
            except Exception as e:
                st.error(f"Erro no processamento: {e}")
                st.session_state.auto_processar = False

if __name__ == "__main__":
    main()
