import os
import time
import tempfile
import streamlit as st
from st_audiorec import st_audiorec
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

    # Componente de Gravação
    st.subheader("1. Gravação")
    wav_audio_data = st_audiorec()

    if wav_audio_data is not None:
        # Reproduzir áudio gravado
        st.audio(wav_audio_data, format='audio/wav')
        
        st.subheader("2. Processamento")
        if st.button("Gerar Ata e Resumo"):
            with st.spinner("A IA está ouvindo e escrevendo a ata..."):
                try:
                    # Salva o áudio temporariamente para enviar ao Gemini
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                        tmp_file.write(wav_audio_data)
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
