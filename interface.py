"""
Interface grafica do downloader de videos

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

from downloader import (
    QUALIDADES,
    DownloadCancelado,
    explicar_erro,
    formatar_bytes,
    montar_opcoes,
)


class Aplicacao(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Downloader de Videos")
        self.geometry("560x460")
        self.resizable(False, False)

        # fila usada para a thread de download conversar com a interface
        self.fila = queue.Queue()
        self.baixando = False
        self.cancelar_evento = threading.Event()
        self.pasta_destino = tk.StringVar(value=os.path.abspath("downloads"))
        self.somente_audio = tk.BooleanVar(value=False)
        self.qualidade = tk.StringVar(value=next(iter(QUALIDADES)))

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
            command=self._atualizar_estado_qualidade,
        ).pack(side="left")

        ttk.Button(
            opcoes,
            text="Escolher pasta...",
            command=self.escolher_pasta,
        ).pack(side="right")

        # qualidade do video
        linha_qualidade = ttk.Frame(moldura)
        linha_qualidade.pack(fill="x", pady=(0, 10))

        ttk.Label(linha_qualidade, text="Qualidade:").pack(side="left")

        self.combo_qualidade = ttk.Combobox(
            linha_qualidade,
            textvariable=self.qualidade,
            values=list(QUALIDADES.keys()),
            state="readonly",
            width=18,
        )
        self.combo_qualidade.pack(side="left", padx=(6, 0))

        ttk.Label(
            moldura,
            textvariable=self.pasta_destino,
            foreground="gray40",
            font=("Segoe UI", 8),
        ).pack(anchor="w")

        # botoes principais
        linha_botoes = ttk.Frame(moldura)
        linha_botoes.pack(fill="x", pady=12)

        self.botao = ttk.Button(
            linha_botoes,
            text="Baixar",
            command=self.iniciar_download,
        )
        self.botao.pack(side="left", fill="x", expand=True)

        self.botao_cancelar = ttk.Button(
            linha_botoes,
            text="Cancelar",
            command=self.cancelar_download,
            state="disabled",
        )
        self.botao_cancelar.pack(side="left", fill="x", expand=True, padx=(8, 0))

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

    def _atualizar_estado_qualidade(self):
        # a escolha de resolucao nao se aplica quando so o audio e baixado
        estado = "disabled" if self.somente_audio.get() else "readonly"
        self.combo_qualidade.configure(state=estado)

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
        self.cancelar_evento.clear()
        self.botao.configure(state="disabled", text="Baixando...")
        self.botao_cancelar.configure(state="normal")
        self.barra["value"] = 0
        self.escrever_log(f"Iniciando: {link}")

        altura_maxima = QUALIDADES[self.qualidade.get()]

        # daemon=True faz a thread morrer junto com a janela
        threading.Thread(
            target=self._tarefa_download,
            args=(
                link,
                self.somente_audio.get(),
                self.pasta_destino.get(),
                altura_maxima,
            ),
            daemon=True,
        ).start()

    def cancelar_download(self):
        if not self.baixando:
            return
        self.cancelar_evento.set()
        self.botao_cancelar.configure(state="disabled")
        self.rotulo_status.configure(text="Cancelando...")

    # ------------------------------------------------------------------
    # thread de download (nao pode tocar na interface diretamente)
    # ------------------------------------------------------------------
    def _tarefa_download(self, link, somente_audio, pasta, altura_maxima):
        def progresso(d):
            if self.cancelar_evento.is_set():
                raise DownloadCancelado()
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

            opcoes = montar_opcoes(somente_audio, altura_maxima)
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

        except DownloadCancelado:
            self.fila.put(("log", "Download cancelado pelo usuario."))
            self.fila.put(("fim", None))

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
                    self.botao_cancelar.configure(state="disabled")
                    if valor is True:
                        self.barra["value"] = 100
                        self.rotulo_status.configure(text="Download concluido!")
                    elif valor is None:
                        self.barra["value"] = 0
                        self.rotulo_status.configure(text="Cancelado.")
                    else:
                        self.barra["value"] = 0
                        self.rotulo_status.configure(text="Falhou. Veja o log.")

        except queue.Empty:
            pass

        # reagenda a propria verificacao
        self.after(100, self._processar_fila)


if __name__ == "__main__":
    Aplicacao().mainloop()
