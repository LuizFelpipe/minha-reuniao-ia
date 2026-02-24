import os
import time
import tempfile
import streamlit as st
from streamlit_mic_recorder import mic_recorder
import google.generativeai as genai
from dotenv import load_dotenv

# Configuração da Página
st.set_page_config(page_title="IA de Reuniões", page_icon="🎙️")

load_dotenv()

def gerar_ata_com_gemini(audio_path, api_key):
    """Envia o áudio para o Gemini e retorna a ata formatada."""
    genai.configure(api_key=api_key)

    # Upload do arquivo para o Google AI Studio
    # Nota: O Gemini processa arquivos temporários. Em produção, idealmente gerenciamos o ciclo de vida do arquivo.
    audio_file = genai.upload_file(path=audio_path)
    
    # Aguarda o processamento do arquivo pelo Google (necessário para arquivos maiores)
    while audio_file.state.name == "PROCESSING":
        time.sleep(2)
        audio_file = genai.get_file(audio_file.name)

    model = genai.GenerativeModel('gemini-1.5-flash')

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

    response = model.generate_content([prompt, audio_file])
    return response.text

def main():
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

    # Componente de Entrada (Gravação ou Upload)
    st.subheader("1. Entrada de Áudio")
    tab_gravacao, tab_upload = st.tabs(["🎙️ Gravar", "📂 Upload Arquivo"])

    with tab_gravacao:
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
                    ata = gerar_ata_com_gemini(tmp_filename, api_key)
                    
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
