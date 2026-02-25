import os
import time
import subprocess
import tempfile
import streamlit as st
from streamlit_mic_recorder import mic_recorder
import google.generativeai as genai
from dotenv import load_dotenv

# Configuração da Página
st.set_page_config(page_title="IA de Reuniões", page_icon="🎙️")

load_dotenv()

# ID do dispositivo de áudio (Mixagem Estéreo) descoberto anteriormente
AUDIO_DEVICE_ID = r'@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\wave_{B94A8C2E-8841-4C4F-A47A-577E3A2003F7}'

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
    # Validação Inicial de Dependências
    if not os.path.exists("ffmpeg.exe"):
        st.error("❌ Arquivo 'ffmpeg.exe' não encontrado na pasta do projeto!")
        st.warning("Por favor, baixe o ffmpeg.exe e coloque na mesma pasta deste script para que a gravação funcione.")
        st.stop()

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

    # Componente de Entrada (Gravação ou Upload)
    st.subheader("1. Entrada de Áudio")
    tab_gravacao, tab_pc, tab_upload = st.tabs(["🎙️ Gravar (Mic)", "🖥️ Gravar (Teams/Meet)", "📂 Upload Arquivo"])

    with tab_gravacao:
        st.info("""
        ℹ️ **Atenção para Reuniões Online (Teams, Zoom, Meet):**
        O gravador do navegador captura apenas o **seu microfone**. Ele não consegue ouvir os outros participantes se você estiver de fone.
        
        👉 **Recomendação:** Grave a reunião pelo próprio Teams/Zoom, baixe o arquivo e use a aba **'Upload Arquivo'** ao lado.
        """)
        # O mic_recorder retorna um dicionário com 'bytes' e outros metadados
        audio_recorder_data = mic_recorder(
            start_prompt="▶️ Iniciar Gravação",
            stop_prompt="⏹️ Parar Gravação",
            just_once=False,
            use_container_width=False,
            format="wav",
            key="recorder"
        )
        # Extrai apenas os bytes se houver gravação
        wav_audio_data = audio_recorder_data['bytes'] if audio_recorder_data else None

    with tab_pc:
        st.info("Esta opção grava o som do sistema (o que você ouve). Ideal para capturar o áudio de reuniões online.")
        
        # Inicializa variáveis de estado para controle da gravação
        if 'proc_gravacao' not in st.session_state:
            st.session_state.proc_gravacao = None
        if 'arquivo_gravado_pc' not in st.session_state:
            st.session_state.arquivo_gravado_pc = None

        # Interface de Controle
        if st.session_state.proc_gravacao is None:
            if st.button("🔴 Iniciar Gravação do PC", type="primary"):
                nome_arquivo = time.strftime("reuniao_pc_%Y-%m-%d_%H-%M-%S.mp3")
                cmd = [
                    '.\\ffmpeg.exe', '-y', '-f', 'dshow', 
                    '-i', f'audio={AUDIO_DEVICE_ID}', 
                    '-vn', nome_arquivo
                ]
                try:
                    # Inicia o ffmpeg sem abrir janela preta (CREATE_NO_WINDOW/USESHOWWINDOW)
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, startupinfo=startupinfo)
                    st.session_state.proc_gravacao = proc
                    st.session_state.arquivo_gravado_pc = nome_arquivo
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao iniciar: {e}")
                    st.warning("""
                    Possíveis causas:
                    1. O dispositivo 'Mixagem Estéreo' está desativado neste PC.
                    2. O ID do dispositivo de áudio mudou (comum ao trocar de computador).
                    """)
        else:
            st.warning(f"🎙️ Gravando... Arquivo: {st.session_state.arquivo_gravado_pc}")
            if st.button("⏹️ Parar Gravação", type="secondary"):
                proc = st.session_state.proc_gravacao
                try:
                    # Envia 'q' para parar suavemente e salvar o arquivo corretamente
                    proc.communicate(input=b'q')
                except:
                    proc.terminate()
                
                st.session_state.proc_gravacao = None
                st.success("Gravação finalizada! O áudio foi selecionado abaixo.")
                time.sleep(1) # Pequena pausa para garantir que o arquivo fechou
                st.rerun()

    with tab_upload:
        uploaded_file = st.file_uploader("Selecione um arquivo (.mp3, .wav, .m4a)", type=["mp3", "wav", "m4a"])

    # Lógica para definir qual áudio processar
    audio_bytes = None
    file_suffix = ".wav" # Padrão para gravação

    if uploaded_file is not None:
        audio_bytes = uploaded_file.getvalue()
        file_suffix = os.path.splitext(uploaded_file.name)[1]
        st.audio(audio_bytes, format=uploaded_file.type)
    elif wav_audio_data is not None:
        audio_bytes = wav_audio_data
    elif st.session_state.get('arquivo_gravado_pc') and os.path.exists(st.session_state.arquivo_gravado_pc):
        # Carrega o arquivo gravado pelo ffmpeg
        arquivo_pc = st.session_state.arquivo_gravado_pc
        st.info(f"Usando arquivo gravado: {arquivo_pc}")
        with open(arquivo_pc, "rb") as f:
            audio_bytes = f.read()
        file_suffix = ".mp3"
        st.audio(audio_bytes, format="audio/mp3")

    if audio_bytes is not None:
        st.subheader("2. Processamento")
        if st.button("Gerar Ata e Resumo"):
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

                except Exception as e:
                    st.error(f"Ocorreu um erro: {e}")

if __name__ == "__main__":
    main()
