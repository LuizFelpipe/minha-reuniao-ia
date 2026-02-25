import os
import time
import subprocess
import re
import tempfile
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv

# Configuração da Página
st.set_page_config(page_title="IA de Reuniões", page_icon="🎙️")

load_dotenv()

def listar_dispositivos_audio(ffmpeg_path):
    """Lista os dispositivos de áudio disponíveis no sistema usando ffmpeg."""
    if not ffmpeg_path or not os.path.exists(ffmpeg_path):
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

    # Upload do arquivo para o Google AI Studio
    # Nota: O Gemini processa arquivos temporários. Em produção, idealmente gerenciamos o ciclo de vida do arquivo.
    audio_file = genai.upload_file(path=audio_path)
    
    # Aguarda o processamento do arquivo pelo Google (necessário para arquivos maiores)
    while audio_file.state.name == "PROCESSING":
        time.sleep(10)
        audio_file = genai.get_file(audio_file.name)

    if audio_file.state.name == "FAILED":
        raise ValueError("O processamento do arquivo de áudio falhou no servidor do Google.")

    # Usa o modelo selecionado pelo usuário
    model = genai.GenerativeModel(model_name)

    prompt = """
    Você é um secretário executivo experiente e eficiente.
    Ouça o áudio desta reunião com atenção.
    
    Sua tarefa é gerar um documento estruturado em Markdown contendo:
    1. **Resumo Executivo**: Um parágrafo conciso sobre o objetivo da reunião.
    2. **Participantes**: Identifique os participantes pelo contexto (se possível) ou liste como "Participante 1", "Participante 2".
    3. **Pontos Principais Discutidos**: Lista com bullets dos tópicos abordados.
    4. **Ações e Tarefas (Action Items)**: Quem deve fazer o quê e, se mencionado, para quando.
    5. **Decisões Tomadas**: O que foi martelo batido.
    
    O tom deve ser profissional e corporativo. Responda em Português do Brasil.
    """

    # Timeout aumentado para 600s (10 min) para dar tempo de processar reuniões longas
    response = model.generate_content([prompt, audio_file], request_options={"timeout": 600})
    return response.text

def main():
    # Detecção inteligente do FFmpeg
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_path = os.path.join(script_dir, "ffmpeg.exe")
    
    if not os.path.exists(ffmpeg_path):
        # Tenta fallback para comando global se não achar local
        import shutil
        if shutil.which("ffmpeg"):
            ffmpeg_path = "ffmpeg"
        else:
            st.error("❌ ffmpeg.exe não encontrado. A gravação não funcionará.")
            ffmpeg_path = None

    st.title("🎙️ Assistente de Reunião com IA")
    st.markdown("Grave sua reunião (Teams, Meet, Presencial) e gere uma ata automaticamente.")

    # Configuração da API Key (Segurança para Web)
    # No Streamlit Cloud, usaremos st.secrets. Localmente, usa .env ou input.
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        # Se não estiver no .env, pede na tela (útil para testar ou compartilhar)
        api_key = st.text_input("Insira sua Google API Key", type="password")

    if not api_key:
        st.warning("Por favor, insira a chave da API para continuar.")
        return

    # Configura a API para listar modelos disponíveis
    genai.configure(api_key=api_key)
    
    try:
        # Lista modelos que suportam geração de conteúdo
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        # Tenta selecionar o Pro ou Flash automaticamente como padrão
        default_index = 0
        for i, m in enumerate(available_models):
            if "gemini-1.5-pro" in m: # Prioridade para o Pro
                default_index = i
                break
        
        model_choice = st.selectbox("Modelo de IA", available_models, index=default_index)
    except Exception as e:
        st.error(f"Erro ao listar modelos: {e}")
        model_choice = "models/gemini-1.5-flash" # Fallback seguro

    # Define a pasta de gravações
    pasta_gravacoes = os.path.join(script_dir, "gravacoes")
    
    if not os.path.exists(pasta_gravacoes):
        os.makedirs(pasta_gravacoes)

    # --- LÓGICA DE GRAVAÇÃO INTEGRADA ---
    st.subheader("1. Gravação e Entrada")
    
    # Inicializa estado da gravação
    if 'gravando' not in st.session_state:
        st.session_state.gravando = False
    if 'processo_gravacao' not in st.session_state:
        st.session_state.processo_gravacao = None
    if 'arquivo_atual' not in st.session_state:
        st.session_state.arquivo_atual = None
    if 'auto_processar' not in st.session_state:
        st.session_state.auto_processar = False

    # Se estiver gravando, mostra apenas o botão de parar
    if st.session_state.gravando:
        st.error(f"🔴 GRAVANDO... ({st.session_state.arquivo_atual})")
        st.info("Minimize esta janela e vá para sua reunião. Não feche o navegador.")
        
        if st.button("⏹️ Parar Gravação e Gerar Ata"):
            proc = st.session_state.processo_gravacao
            if proc:
                try:
                    proc.communicate(input=b'q', timeout=5)
                except:
                    proc.terminate()
            
            st.session_state.gravando = False
            st.session_state.processo_gravacao = None
            st.session_state.auto_processar = True # Gatilho para processamento automático
            st.rerun()
            
    else:
        # Se NÃO estiver gravando, mostra abas de opções
        tab_nova, tab_existente, tab_upload = st.tabs(["🔴 Nova Gravação", "📂 Gravações Antigas", "📤 Upload Manual"])
        
        with tab_nova:
            if ffmpeg_path:
                dispositivos = listar_dispositivos_audio(ffmpeg_path)
                if dispositivos:
                    # Tenta achar Mixagem Estéreo por padrão
                    idx = 0
                    for i, d in enumerate(dispositivos):
                        if "mixagem" in d.lower() or "stereo" in d.lower():
                            idx = i
                            break
                    
                    device = st.selectbox("Fonte de Áudio:", dispositivos, index=idx)
                    
                    if st.button("Iniciar Gravação"):
                        nome_arquivo = time.strftime("reuniao_%Y-%m-%d_%H-%M-%S.mp3")
                        caminho_completo = os.path.join(pasta_gravacoes, nome_arquivo)
                        
                        cmd = [
                            ffmpeg_path, '-y', '-f', 'dshow', 
                            '-i', f'audio={device}', 
                            '-vn', caminho_completo
                        ]
                        
                        # Inicia processo sem bloquear a UI
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, startupinfo=startupinfo)
                        
                        st.session_state.processo_gravacao = proc
                        st.session_state.gravando = True
                        st.session_state.arquivo_atual = nome_arquivo
                        st.rerun()
                else:
                    st.warning("Nenhum dispositivo de áudio encontrado. Verifique se o ffmpeg está funcionando.")
            else:
                st.error("FFmpeg não configurado.")

    audio_bytes = None
    file_suffix = ".mp3"

    with tab_local:
        st.info("Use o **Gravador.bat** para gravar a reunião. Os arquivos aparecerão aqui automaticamente.")
        
        # Lista arquivos na pasta
        arquivos = [f for f in os.listdir(pasta_gravacoes) if f.endswith(('.mp3', '.wav', '.m4a'))]
        arquivos.sort(key=lambda x: os.path.getmtime(os.path.join(pasta_gravacoes, x)), reverse=True)
        
        if arquivos:
            # Se acabamos de gravar, seleciona o arquivo novo automaticamente
            idx_selecao = 0
            if st.session_state.auto_processar and st.session_state.arquivo_atual in arquivos:
                idx_selecao = arquivos.index(st.session_state.arquivo_atual)

            arquivo_selecionado = st.selectbox("Selecione a gravação:", arquivos, index=idx_selecao)
            
            if arquivo_selecionado:
                caminho_arquivo = os.path.join(pasta_gravacoes, arquivo_selecionado)
                st.audio(caminho_arquivo)
                with open(caminho_arquivo, "rb") as f:
                    audio_bytes = f.read()
                    
                # Se for processamento automático, define o sufixo corretamente
                file_suffix = os.path.splitext(arquivo_selecionado)[1]
        else:
            st.warning("Nenhuma gravação encontrada na pasta 'gravacoes'.")
            if st.button("🔄 Atualizar Lista"):
                st.rerun()

        with tab_upload:
            uploaded_file = st.file_uploader("Selecione um arquivo (.mp3, .wav, .m4a, .webm, .mp4)", type=["mp3", "wav", "m4a", "webm", "mp4"])
            if uploaded_file is not None:
                audio_bytes = uploaded_file.getvalue()
                file_suffix = os.path.splitext(uploaded_file.name)[1]
                st.audio(audio_bytes, format=uploaded_file.type if "audio" in uploaded_file.type else "video/webm")

    # --- PROCESSAMENTO ---
    if audio_bytes is not None:
        st.subheader("2. Processamento")
        
        # Botão manual OU Gatilho automático
        if st.button("Gerar Ata e Resumo") or st.session_state.auto_processar:
            with st.spinner("A IA está ouvindo e escrevendo a ata..."):
                try:
                    # Salva o áudio temporariamente para enviar ao Gemini
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
                        tmp_file.write(audio_bytes)
                        tmp_filename = tmp_file.name

                    # Chama a IA
                    ata = gerar_ata_com_gemini(tmp_filename, api_key, model_choice)
                    
                    # Exibe o resultado
                    st.success("Ata gerada com sucesso!")
                    st.markdown("---")
                    st.markdown(ata)
                    
                    # Botão de Download
                    st.download_button(
                        label="Baixar Ata (.md)",
                        data=ata,
                        file_name="ata_reuniao.md",
                        mime="text/markdown"
                    )
                    
                    # Limpeza
                    os.unlink(tmp_filename)
                    
                    # Reseta o gatilho automático para não rodar de novo ao recarregar
                    st.session_state.auto_processar = False

                except Exception as e:
                    st.error(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    main()
