import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import os
import time
import re
import threading

class GravadorReuniao:
    def __init__(self, root):
        self.root = root
        self.root.title("Gravador de Reuniões")
        self.root.geometry("400x350")
        
        self.processo = None
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.ffmpeg_path = os.path.join(self.script_dir, "ffmpeg.exe")
        self.pasta_gravacoes = os.path.join(self.script_dir, "gravacoes")

        # Garante que a pasta de gravações existe
        if not os.path.exists(self.pasta_gravacoes):
            os.makedirs(self.pasta_gravacoes)
        
        # Título
        tk.Label(root, text="Gravador de Teams/Meet", font=("Arial", 14)).pack(pady=10)

        # Seleção de Dispositivo
        tk.Label(root, text="Selecione a fonte de áudio (Mixagem Estéreo):", font=("Arial", 9)).pack(pady=5)
        self.combo_dispositivos = ttk.Combobox(root, width=40)
        self.combo_dispositivos.pack(pady=5)
        
        # Botão Atualizar Lista
        tk.Button(root, text="🔄 Atualizar Lista", command=self.listar_dispositivos, font=("Arial", 8)).pack(pady=2)

        # Botão Iniciar
        self.btn_iniciar = tk.Button(root, text="🔴 Iniciar Gravação", command=self.iniciar, bg="#ffcccc", font=("Arial", 11, "bold"), width=25, height=2)
        self.btn_iniciar.pack(pady=20)
        
        # Botão Parar
        self.btn_parar = tk.Button(root, text="⬛ Parar e Salvar", command=self.parar, bg="#dddddd", font=("Arial", 11), width=25, height=2, state=tk.DISABLED)
        self.btn_parar.pack(pady=5)
        
        # Status
        self.lbl_status = tk.Label(root, text="Pronto para gravar", fg="gray")
        self.lbl_status.pack(pady=10)

        # Carrega dispositivos ao iniciar
        self.listar_dispositivos()

    def listar_dispositivos(self):
        if not os.path.exists(self.ffmpeg_path):
            messagebox.showerror("Erro", "ffmpeg.exe não encontrado na pasta do projeto!")
            return

        try:
            cmd = [self.ffmpeg_path, '-list_devices', 'true', '-f', 'dshow', '-i', 'dummy']
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
            
            self.combo_dispositivos['values'] = devices
            if devices:
                # Tenta selecionar automaticamente Mixagem Estéreo
                for i, dev in enumerate(devices):
                    if "mixagem" in dev.lower() or "stereo" in dev.lower():
                        self.combo_dispositivos.current(i)
                        break
                if self.combo_dispositivos.current() == -1:
                    self.combo_dispositivos.current(0)
                    
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao listar dispositivos: {e}")

    def iniciar(self):
        device_name = self.combo_dispositivos.get()
        if not device_name:
            messagebox.showwarning("Atenção", "Selecione um dispositivo de áudio!")
            return

        # Nome do arquivo com data e hora para não substituir o anterior
        nome_arquivo = time.strftime("reuniao_%Y-%m-%d_%H-%M-%S.mp3")
        caminho_completo = os.path.join(self.pasta_gravacoes, nome_arquivo)
        
        # Comando ffmpeg montado
        cmd = [
            self.ffmpeg_path, 
            '-y', 
            '-f', 'dshow', 
            '-i', f'audio={device_name}', 
            '-vn', 
            caminho_completo
        ]
        
        try:
            # Inicia o ffmpeg em segundo plano
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.processo = subprocess.Popen(cmd, stdin=subprocess.PIPE, startupinfo=startupinfo)
            
            self.lbl_status.config(text=f"GRAVANDO...\nArquivo: {nome_arquivo}", fg="red")
            self.btn_iniciar.config(state=tk.DISABLED)
            self.btn_parar.config(state=tk.NORMAL, bg="#ff4444", fg="white")
            self.combo_dispositivos.config(state=tk.DISABLED)
            
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível iniciar o gravador:\n{e}")

    def parar(self):
        if self.processo:
            try:
                # Envia o comando 'q' para o ffmpeg fechar o arquivo corretamente
                self.processo.communicate(input=b'q', timeout=5)
            except:
                self.processo.terminate()
            
            self.processo = None
            
            self.lbl_status.config(text="Salvo na pasta 'gravacoes'!", fg="green")
            self.btn_iniciar.config(state=tk.NORMAL)
            self.btn_parar.config(state=tk.DISABLED, bg="#dddddd")
            self.combo_dispositivos.config(state=tk.NORMAL)
            messagebox.showinfo("Sucesso", "Gravação finalizada!\nAgora abra a interface Web para gerar a ata.")

if __name__ == "__main__":
    root = tk.Tk()
    app = GravadorReuniao(root)
    root.mainloop()