import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import time

class GravadorReuniao:
    def __init__(self, root):
        self.root = root
        self.root.title("Gravador de Reuniões")
        self.root.geometry("350x200")
        
        self.processo = None
        
        # Título
        tk.Label(root, text="Gravador de Teams/Meet", font=("Arial", 14)).pack(pady=10)

        # Botão Iniciar
        self.btn_iniciar = tk.Button(root, text="🔴 Iniciar Gravação", command=self.iniciar, bg="#dddddd", font=("Arial", 10), width=20)
        self.btn_iniciar.pack(pady=10)
        
        # Botão Parar
        self.btn_parar = tk.Button(root, text="⬛ Parar e Salvar", command=self.parar, bg="#dddddd", font=("Arial", 10), width=20, state=tk.DISABLED)
        self.btn_parar.pack(pady=10)
        
        # Status
        self.lbl_status = tk.Label(root, text="Pronto para gravar", fg="gray")
        self.lbl_status.pack(pady=5)

    def iniciar(self):
        # Nome do arquivo com data e hora para não substituir o anterior
        nome_arquivo = time.strftime("reuniao_%Y-%m-%d_%H-%M-%S.mp3")
        
        # O ID exato da sua Mixagem Estéreo (conforme seu log anterior)
        audio_device = '@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\wave_{B94A8C2E-8841-4C4F-A47A-577E3A2003F7}'
        
        # Comando ffmpeg montado
        cmd = [
            '.\\ffmpeg.exe', 
            '-y', 
            '-f', 'dshow', 
            '-i', f'audio={audio_device}', 
            '-vn', 
            nome_arquivo
        ]
        
        try:
            # Inicia o ffmpeg em segundo plano
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.processo = subprocess.Popen(cmd, stdin=subprocess.PIPE, startupinfo=startupinfo)
            
            self.lbl_status.config(text=f"Gravando: {nome_arquivo}", fg="red")
            self.btn_iniciar.config(state=tk.DISABLED)
            self.btn_parar.config(state=tk.NORMAL, bg="#ffcccc")
            
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível iniciar o gravador:\n{e}")

    def parar(self):
        if self.processo:
            # Envia o comando 'q' para o ffmpeg fechar o arquivo corretamente
            self.processo.communicate(input=b'q')
            self.processo = None
            
            self.lbl_status.config(text="Gravação salva com sucesso!", fg="green")
            self.btn_iniciar.config(state=tk.NORMAL)
            self.btn_parar.config(state=tk.DISABLED, bg="#dddddd")
            messagebox.showinfo("Sucesso", "Áudio salvo na pasta do projeto!")

if __name__ == "__main__":
    root = tk.Tk()
    app = GravadorReuniao(root)
    root.mainloop()