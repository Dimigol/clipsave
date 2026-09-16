"""
Downloader de videos do YouTube
Trabalho de faculdade

Uso:
    python downloader.py                 -> modo interativo (pergunta o link)
    python downloader.py <link>          -> baixa direto
    python downloader.py <link> -a       -> baixa apenas o audio (mp3)
"""

import os
import sys

from yt_dlp import YoutubeDL

PASTA_DESTINO = "downloads"


def formatar_bytes(n):
    """Converte bytes para uma unidade legivel (KB, MB, GB)."""
    if not n:
        return "?"
    for unidade in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} TB"


def progresso(d):
    """Callback chamado pelo yt-dlp durante o download."""
    if d["status"] == "downloading":
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        baixado = d.get("downloaded_bytes", 0)
        pct = (baixado / total * 100) if total else 0
        print(
            f"\rBaixando: {pct:5.1f}%  "
            f"({formatar_bytes(baixado)} de {formatar_bytes(total)})",
            end="",
            flush=True,
        )
    elif d["status"] == "finished":
        print("\rFaixa baixada. Processando...                        ")


def alvo_imitacao():
    """
    Retorna o alvo de imitacao de navegador, ou None se indisponivel.

    Alguns sites (TikTok, por exemplo) so respondem corretamente quando a
    requisicao tem a assinatura TLS de um navegador real. O yt-dlp faz isso
    atraves da biblioteca opcional curl_cffi. Se ela nao estiver instalada,
    seguimos sem imitacao: o YouTube funciona normalmente assim.
    """
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget

        return ImpersonateTarget("chrome")
    except ImportError:
        return None


def montar_opcoes(somente_audio=False):
    """Monta o dicionario de configuracao do yt-dlp."""
    opcoes = {
        "outtmpl": os.path.join(PASTA_DESTINO, "%(title)s.%(ext)s"),
        "progress_hooks": [progresso],
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
    }

    alvo = alvo_imitacao()
    if alvo is not None:
        opcoes["impersonate"] = alvo

    if somente_audio:
        opcoes["format"] = "bestaudio/best"
        opcoes["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        # melhor video + melhor audio, unidos em mp4
        opcoes["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        opcoes["merge_output_format"] = "mp4"

    return opcoes


def baixar(link, somente_audio=False):
    """Baixa o video (ou audio) do link informado."""
    os.makedirs(PASTA_DESTINO, exist_ok=True)

    with YoutubeDL(montar_opcoes(somente_audio)) as ydl:
        # extrai os metadados uma unica vez, sem baixar
        info = ydl.extract_info(link, download=False)

        print("\n--- Informacoes do video ---")
        print(f"Titulo : {info.get('title')}")
        print(f"Canal  : {info.get('uploader')}")
        duracao = info.get("duration") or 0
        print(f"Duracao: {duracao // 60}min {duracao % 60}s")
        print("----------------------------\n")

        # reaproveita o resultado acima em vez de extrair de novo.
        # alem de evitar uma requisicao redundante, alguns sites (TikTok)
        # recusam a segunda extracao seguida da mesma URL.
        ydl.process_ie_result(info, download=True)

    print("Download concluido.")

    caminho = os.path.abspath(PASTA_DESTINO)
    print(f"\nArquivo salvo em: {caminho}")


def explicar_erro(mensagem):
    """Traduz os erros mais comuns do yt-dlp para algo compreensivel."""
    m = mensagem.lower()

    if "rehydration" in m or "unexpected response" in m:
        return (
            "\nO site respondeu de forma inesperada. Isso costuma acontecer\n"
            "quando ele limita requisicoes repetidas vindas do mesmo\n"
            "computador. Aguarde alguns minutos e tente de novo, sem\n"
            "repetir a tentativa varias vezes seguidas."
        )
    if "not available" in m:
        return (
            "\nO video pode ter sido removido, estar privado, ou o site\n"
            "pode estar restringindo o acesso a esse conteudo."
        )
    if "ffmpeg" in m:
        return (
            "\nO ffmpeg e necessario para juntar video e audio.\n"
            "Instale com: winget install --id Gyan.FFmpeg -e"
        )
    if "unsupported url" in m:
        return (
            "\nO yt-dlp nao reconheceu esse endereco. Verifique se o link\n"
            "aponta para um video especifico, e nao para uma pagina de\n"
            "feed, perfil ou busca. Exemplos validos:\n"
            "  https://www.youtube.com/watch?v=XXXXXXXXXXX\n"
            "  https://www.tiktok.com/@usuario/video/1234567890\n"
            "Use a opcao 'Compartilhar > Copiar link' do proprio site."
        )

    return ""


def main():
    print("=" * 45)
    print("   DOWNLOADER DE VIDEOS DO YOUTUBE")
    print("=" * 45)

    args = [a for a in sys.argv[1:]]
    somente_audio = "-a" in args or "--audio" in args
    links = [a for a in args if not a.startswith("-")]

    if links:
        link = links[0]
    else:
        link = input("\nCole o link do video: ").strip()
        if not somente_audio:
            resposta = input("Baixar apenas o audio (mp3)? [s/N]: ").strip().lower()
            somente_audio = resposta == "s"

    if not link:
        print("Erro: nenhum link informado.")
        return 1

    try:
        baixar(link, somente_audio)
    except KeyboardInterrupt:
        print("\nDownload cancelado pelo usuario.")
        return 1
    except Exception as erro:
        print(f"\nErro ao baixar: {erro}")
        print(explicar_erro(str(erro)))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
