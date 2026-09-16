"""
Interface grafica do downloader de videos
Trabalho de faculdade

Uso:
    python interface.py

Reaproveita a logica de download do modulo downloader.py.
A janela roda na thread principal e o download numa thread separada,
para que a interface nao congele durante a operacao.
"""

import os
import queue
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from yt_dlp import YoutubeDL

# o yt-dlp colore as mensagens com codigos ANSI, que o Tkinter nao
# interpreta e exibiria como lixo do tipo "[0;31m" no log
ANSI = re.compile(r"\x1b\[[0-9;]*m")

from downloader import explicar_erro, formatar_bytes, montar_opcoes


class Aplicacao(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Downloader de Videos")
        self.geometry("560x420")
        self.resizable(False, False)

        # fila usada para a thread de download conversar com a interface
        self.fila = queue.Queue()
        self.baixando = False
        self.pasta_destino = tk.StringVar(value=os.path.abspath("downloads"))
        self.somente_audio = tk.BooleanVar(value=False)

        self._montar_widgets()
        self.after(100, self._processar_fila)

    # ------------------------------------------------------------------
    # construcao da interface
    # ------------------------------------------------------------------
    def _montar_widgets(self):
        moldura = ttk.Frame(self, padding=15)
        moldura.pack(fill="both", expand=True)

        ttk.Label(
            moldura,
            text="Downloader de Videos",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            moldura,
            text="Cole o link do video abaixo",
            foreground="gray30",
        ).pack(anchor="w", pady=(0, 10))

        # campo do link
        self.campo_link = ttk.Entry(moldura, font=("Segoe UI", 10))
        self.campo_link.pack(fill="x")
        self.campo_link.focus()
        self.campo_link.bind("<Return>", lambda _e: self.iniciar_download())

        # opcoes
        opcoes = ttk.Frame(moldura)
        opcoes.pack(fill="x", pady=10)

        ttk.Checkbutton(
            opcoes,
            text="Baixar apenas o audio (mp3)",
            variable=self.somente_audio,
        ).pack(side="left")

        ttk.Button(
            opcoes,
            text="Escolher pasta...",
            command=self.escolher_pasta,
        ).pack(side="right")

        ttk.Label(
            moldura,
            textvariable=self.pasta_destino,
            foreground="gray40",
            font=("Segoe UI", 8),
        ).pack(anchor="w")

        # botao principal
        self.botao = ttk.Button(
            moldura,
            text="Baixar",
            command=self.iniciar_download,
        )
        self.botao.pack(fill="x", pady=12)

        # barra de progresso
        self.barra = ttk.Progressbar(moldura, maximum=100)
        self.barra.pack(fill="x")

        self.rotulo_status = ttk.Label(moldura, text="Aguardando link...")
        self.rotulo_status.pack(anchor="w", pady=(4, 8))

        # area de log
        self.log = tk.Text(moldura, height=8, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # acoes da interface
    # ------------------------------------------------------------------
    def escolher_pasta(self):
        pasta = filedialog.askdirectory(initialdir=self.pasta_destino.get())
        if pasta:
            self.pasta_destino.set(pasta)

    def escrever_log(self, texto):
        texto = ANSI.sub("", str(texto))
        self.log.configure(state="normal")
        self.log.insert("end", texto + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def iniciar_download(self):
        if self.baixando:
            return

        link = self.campo_link.get().strip()
        if not link:
            messagebox.showwarning("Atencao", "Informe o link do video.")
            return

        self.baixando = True
        self.botao.configure(state="disabled", text="Baixando...")
        self.barra["value"] = 0
        self.escrever_log(f"Iniciando: {link}")

        # daemon=True faz a thread morrer junto com a janela
        threading.Thread(
            target=self._tarefa_download,
            args=(link, self.somente_audio.get(), self.pasta_destino.get()),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # thread de download (nao pode tocar na interface diretamente)
    # ------------------------------------------------------------------
    def _tarefa_download(self, link, somente_audio, pasta):
        def progresso(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                baixado = d.get("downloaded_bytes", 0)
                pct = (baixado / total * 100) if total else 0
                self.fila.put(("progresso", pct))
                self.fila.put((
                    "status",
                    f"{pct:.1f}%  ({formatar_bytes(baixado)} de {formatar_bytes(total)})",
                ))
            elif d["status"] == "finished":
                self.fila.put(("status", "Faixa baixada. Processando..."))

        try:
            os.makedirs(pasta, exist_ok=True)

            opcoes = montar_opcoes(somente_audio)
            opcoes["outtmpl"] = os.path.join(pasta, "%(title)s.%(ext)s")
            opcoes["progress_hooks"] = [progresso]

            with YoutubeDL(opcoes) as ydl:
                info = ydl.extract_info(link, download=False)
                duracao = info.get("duration") or 0
                self.fila.put(("log", f"Titulo : {info.get('title')}"))
                self.fila.put(("log", f"Canal  : {info.get('uploader')}"))
                self.fila.put(
                    ("log", f"Duracao: {duracao // 60}min {duracao % 60}s")
                )
                # reaproveita a extracao acima em vez de repeti-la
                ydl.process_ie_result(info, download=True)

            self.fila.put(("log", f"Concluido. Salvo em: {pasta}"))
            self.fila.put(("fim", True))

        except Exception as erro:
            self.fila.put(("log", f"ERRO: {erro}"))
            explicacao = explicar_erro(str(erro))
            if explicacao:
                self.fila.put(("log", explicacao.strip()))
            self.fila.put(("fim", False))

    # ------------------------------------------------------------------
    # ponte entre a thread e a interface
    # ------------------------------------------------------------------
    def _processar_fila(self):
        try:
            while True:
                tipo, valor = self.fila.get_nowait()

                if tipo == "progresso":
                    self.barra["value"] = valor
                elif tipo == "status":
                    self.rotulo_status.configure(text=valor)
                elif tipo == "log":
                    self.escrever_log(valor)
                elif tipo == "fim":
                    self.baixando = False
                    self.botao.configure(state="normal", text="Baixar")
                    if valor:
                        self.barra["value"] = 100
                        self.rotulo_status.configure(text="Download concluido!")
                    else:
                        self.barra["value"] = 0
                        self.rotulo_status.configure(text="Falhou. Veja o log.")

        except queue.Empty:
            pass

        # reagenda a propria verificacao
        self.after(100, self._processar_fila)


if __name__ == "__main__":
    Aplicacao().mainloop()
