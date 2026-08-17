"""Motor de download do BaixaFacil.

Mudanca central em relacao a versao antiga: o yt-dlp e usado como BIBLIOTECA
(`import yt_dlp`), nao como binario chamado por subprocess.

Antes:  subprocess.Popen(["yt-dlp", ...])
        -> dependia de um executavel externo, com shebang apontando pro venv
           da maquina de quem buildou. Em outro computador: FileNotFoundError
           e a caixa "yt-dlp nao encontrado! Instale com: pip install yt-dlp".

Agora:  yt_dlp.YoutubeDL(opcoes).download([url])
        -> o modulo vai congelado dentro do app pelo PyInstaller. Nao ha
           binario pra sumir, nem PATH pra dar errado, nem pip pro usuario rodar.

De quebra, o progresso vem de progress_hooks (numeros exatos) em vez de regex
em cima do stdout.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable

import yt_dlp

from . import spotify
from .binarios import Ambiente

# Qualidade de audio no padrao do yt-dlp: 0 = melhor, 9 = pior.
QUALIDADE_AUDIO = {"Alta": "0", "Normal": "5", "Baixa": "9"}

# Ordenacao de formato de video. "res" sozinho = maior resolucao disponivel.
QUALIDADE_VIDEO = {
    "Alta": "res,vcodec:h264,acodec:aac",
    "Normal": "res:720,vcodec:h264,acodec:aac",
    "Baixa": "+res,vcodec:h264,acodec:aac",
}

# Sites confirmados funcionando. O yt-dlp suporta mais de mil, entao a lista
# nao e uma trava: e o que a gente promete e testa.
SITES_SUPORTADOS = (
    "YouTube", "YouTube Music", "Spotify (via busca)", "Instagram",
    "Facebook", "TikTok", "X/Twitter", "Vimeo", "Twitch", "SoundCloud",
    "Dailymotion", "Reddit", "Kwai", "Pinterest",
)


@dataclass
class Progresso:
    """Uma foto do andamento, enviada pra interface."""
    porcentagem: float = 0.0
    titulo: str = ""
    velocidade: str = ""
    faltando: str = ""
    item_atual: int = 1
    total_itens: int = 1
    etapa: str = "baixando"   # baixando | convertendo | concluido


@dataclass
class Pedido:
    url: str
    destino: str
    qualidade: str = "Alta"
    somente_audio: bool = False
    playlist: bool = False
    # Navegador de onde puxar cookies ("chrome", "firefox", "safari", "edge"...).
    # Vazio = nao usar cookies. Ver NAVEGADORES.
    navegador: str = ""
    # Preenchido quando a origem e o Spotify, so pra mostrar na interface.
    rotulo_origem: str = ""
    musicas_spotify: list[spotify.Musica] = field(default_factory=list)


# Sites que praticamente exigem estar logado. A interface usa esta lista pra
# sugerir o login do navegador ANTES de o usuario tomar erro.
EXIGEM_LOGIN = ("instagram.com", "facebook.com", "fb.watch", "x.com", "twitter.com")

NAVEGADORES = ("chrome", "brave", "edge", "firefox", "opera", "safari", "vivaldi", "chromium")


def precisa_de_login(url: str) -> bool:
    return any(dominio in url.lower() for dominio in EXIGEM_LOGIN)


class ErroDownload(Exception):
    """Erro ja traduzido pra uma frase que o usuario entende."""


def _humanizar_erro(bruto: str) -> str:
    """Converte o erro cru do yt-dlp em algo acionavel em portugues."""
    b = bruto.lower()
    if "ffmpeg" in b and ("not found" in b or "nao encontrado" in b):
        return ("O conversor de áudio/vídeo não foi encontrado dentro do app. "
                "Reinstale o BaixaFácil pela loja da FlowCore.")
    if "private video" in b or "video privado" in b:
        return "Esse vídeo é privado. Só o dono consegue baixar."
    if "members-only" in b or "join this channel" in b:
        return "Esse conteúdo é exclusivo pra membros do canal."
    if "sign in to confirm your age" in b or "age-restricted" in b or "age restricted" in b:
        return "Esse vídeo tem restrição de idade e exige login no site de origem."
    if "sign in to confirm" in b or "not a bot" in b:
        return ("O YouTube pediu verificação pra este vídeo. Tente de novo em alguns "
                "minutos ou use outro link.")
    if "video unavailable" in b or "this video is unavailable" in b:
        return "Esse vídeo não está disponível (removido ou bloqueado na sua região)."
    if "unsupported url" in b:
        return "Não sei baixar desse site ainda. Confira se o link está completo."
    if "no video formats" in b or "requested format is not available" in b:
        return "Esse link não tem um formato que eu consiga baixar."
    if "unable to download webpage" in b or "getaddrinfo" in b or "connection" in b:
        return "Não consegui acessar a internet. Confira sua conexão e tente de novo."
    if "login required" in b or "cookies" in b:
        return ("Esse conteúdo exige estar logado no site. Perfis privados do "
                "Instagram e Facebook não dão pra baixar.")
    if "http error 404" in b:
        return "Esse link não existe mais (404)."
    # Sem tradutor especifico: devolve enxuto, sem stack trace.
    limpo = re.sub(r"\s+", " ", bruto).strip()
    return limpo[:200]


class _Silencio:
    """Engole o log do yt-dlp; quem fala com o usuario e a interface."""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


class Motor:
    def __init__(self, ambiente: Ambiente | None = None) -> None:
        self.ambiente = ambiente or Ambiente()
        self._cancelar = False

    def cancelar(self) -> None:
        self._cancelar = True

    # ── Analise do link ──────────────────────────────────────────────────

    def preparar(self, url: str, destino: str, qualidade: str,
                 somente_audio: bool, playlist: bool, navegador: str = "") -> Pedido:
        """Monta o pedido, resolvendo o Spotify quando for o caso."""
        url = url.strip()
        if not url:
            raise ErroDownload("Cole um link primeiro.")

        if spotify.eh_spotify(url):
            # Spotify e audio. Forcar video aqui so geraria confusao.
            resultado = spotify.resolver(url)
            return Pedido(
                url=url, destino=destino, qualidade=qualidade,
                somente_audio=True, playlist=len(resultado.musicas) > 1,
                navegador=navegador,
                rotulo_origem=f"Spotify: {resultado.nome}",
                musicas_spotify=resultado.musicas,
            )

        if not re.match(r"^https?://", url):
            raise ErroDownload("O link precisa começar com http:// ou https://")

        return Pedido(url=url, destino=destino, qualidade=qualidade,
                      somente_audio=somente_audio, playlist=playlist,
                      navegador=navegador)

    # ── Opcoes do yt-dlp ─────────────────────────────────────────────────

    def _opcoes(self, pedido: Pedido, aoProgresso: Callable[[Progresso], None],
                modelo_saida: str) -> dict:
        opcoes: dict = {
            "outtmpl": modelo_saida,
            "noplaylist": not pedido.playlist,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": _Silencio(),
            "progress_hooks": [self._gancho_progresso(aoProgresso)],
            "postprocessor_hooks": [self._gancho_pos(aoProgresso)],
            "retries": 5,
            "fragment_retries": 5,
            "socket_timeout": 30,
            "ignoreerrors": pedido.playlist,   # 1 faixa ruim nao derruba a playlist
            "restrictfilenames": False,
            "windowsfilenames": True,          # nomes que sobrevivem no Windows
            "overwrites": False,
            "continuedl": True,
        }

        if self.ambiente.pasta_ffmpeg:
            opcoes["ffmpeg_location"] = self.ambiente.pasta_ffmpeg

        # O cliente "web" do YouTube devolve 403 Forbidden nas trilhas de audio
        # (medido em 17/08/2026: audio falhava, video passava). O cliente
        # "android" entrega os mesmos formatos sem o bloqueio. Deixamos "web" e
        # "web_safari" na fila como reserva, caso o android pare um dia.
        opcoes["extractor_args"] = {
            "youtube": {"player_client": ["android", "web_safari", "web"]}
        }

        # Cookies do navegador do proprio usuario. E o unico jeito de baixar do
        # Instagram e de conteudo restrito do Facebook/X: o site so entrega a
        # midia pra quem esta logado. Fica DESLIGADO por padrao e nada e
        # enviado pra lugar nenhum, o yt-dlp le e usa localmente.
        if pedido.navegador:
            opcoes["cookiesfrombrowser"] = (pedido.navegador, None, None, None)

        if pedido.somente_audio:
            opcoes["format"] = "bestaudio/best"
            opcoes["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": QUALIDADE_AUDIO[pedido.qualidade],
                },
                # Capa e metadados fazem o arquivo aparecer bonito no player.
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail", "already_have_thumbnail": False},
            ]
            opcoes["writethumbnail"] = True
        else:
            opcoes["format"] = "bestvideo*+bestaudio/best"
            opcoes["format_sort"] = QUALIDADE_VIDEO[pedido.qualidade].split(",")
            opcoes["merge_output_format"] = "mp4"
            opcoes["postprocessors"] = [
                {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
                {"key": "FFmpegMetadata", "add_metadata": True},
            ]

        return opcoes

    # ── Ganchos de progresso ─────────────────────────────────────────────

    def _gancho_progresso(self, aoProgresso):
        def gancho(d):
            if self._cancelar:
                raise ErroDownload("cancelado")
            if d.get("status") != "downloading":
                return
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            baixado = d.get("downloaded_bytes") or 0
            pct = (baixado / total * 100) if total else 0.0
            info = d.get("info_dict") or {}
            aoProgresso(Progresso(
                porcentagem=pct,
                titulo=info.get("title") or "",
                velocidade=self._formatar_velocidade(d.get("speed")),
                faltando=self._formatar_tempo(d.get("eta")),
                etapa="baixando",
            ))
        return gancho

    def _gancho_pos(self, aoProgresso):
        def gancho(d):
            if d.get("status") == "started":
                info = d.get("info_dict") or {}
                aoProgresso(Progresso(
                    porcentagem=100.0,
                    titulo=info.get("title") or "",
                    etapa="convertendo",
                ))
        return gancho

    @staticmethod
    def _formatar_velocidade(bps) -> str:
        if not bps:
            return ""
        if bps >= 1024 ** 2:
            return f"{bps / 1024 ** 2:.1f} MB/s"
        return f"{bps / 1024:.0f} KB/s"

    @staticmethod
    def _formatar_tempo(segundos) -> str:
        if not segundos:
            return ""
        segundos = int(segundos)
        if segundos >= 60:
            return f"{segundos // 60}min {segundos % 60}s"
        return f"{segundos}s"

    # ── Execucao ─────────────────────────────────────────────────────────

    def baixar(self, pedido: Pedido, aoProgresso: Callable[[Progresso], None]) -> int:
        """Executa o download. Devolve quantos itens foram salvos."""
        self._cancelar = False

        if pedido.musicas_spotify:
            return self._baixar_do_spotify(pedido, aoProgresso)

        modelo = os.path.join(pedido.destino, "%(title)s.%(ext)s")
        if pedido.playlist:
            modelo = os.path.join(
                pedido.destino, "%(playlist_title)s", "%(playlist_index)02d - %(title)s.%(ext)s"
            )
        opcoes = self._opcoes(pedido, aoProgresso, modelo)

        try:
            with yt_dlp.YoutubeDL(opcoes) as ydl:
                codigo = ydl.download([pedido.url])
        except ErroDownload:
            raise
        except yt_dlp.utils.DownloadError as exc:
            raise ErroDownload(_humanizar_erro(str(exc))) from exc
        except Exception as exc:
            raise ErroDownload(_humanizar_erro(str(exc))) from exc

        if codigo != 0 and not pedido.playlist:
            raise ErroDownload("Não consegui baixar esse link. Confira se ele ainda funciona.")
        return 1

    def _baixar_do_spotify(self, pedido: Pedido,
                           aoProgresso: Callable[[Progresso], None]) -> int:
        """Uma busca por musica, e baixa o melhor resultado de cada."""
        total = len(pedido.musicas_spotify)
        salvos = 0
        falhas: list[str] = []

        for indice, musica in enumerate(pedido.musicas_spotify, start=1):
            if self._cancelar:
                break

            def repassar(p: Progresso, i=indice, m=musica):
                p.item_atual = i
                p.total_itens = total
                p.titulo = p.titulo or m.nome_arquivo
                aoProgresso(p)

            # Nome do arquivo vem do Spotify (artista - titulo), nao do YouTube,
            # que costuma ter "(Official Video)", "HD", "lyrics" e afins no meio.
            nome = _limpar_nome(musica.nome_arquivo)
            modelo = os.path.join(pedido.destino, f"{nome}.%(ext)s")

            sub = Pedido(url="", destino=pedido.destino, qualidade=pedido.qualidade,
                         somente_audio=True, playlist=False, navegador=pedido.navegador)
            opcoes = self._opcoes(sub, repassar, modelo)
            # ytsearch1 = pega so o primeiro resultado da busca.
            alvo = f"ytsearch1:{musica.busca}"

            try:
                with yt_dlp.YoutubeDL(opcoes) as ydl:
                    ydl.download([alvo])
                salvos += 1
            except ErroDownload:
                raise
            except Exception:
                falhas.append(musica.nome_arquivo)

        if salvos == 0:
            detalhe = f" Falharam: {', '.join(falhas[:3])}." if falhas else ""
            raise ErroDownload(f"Não consegui encontrar nenhuma dessas músicas.{detalhe}")
        return salvos


def _limpar_nome(nome: str) -> str:
    """Tira o que o sistema de arquivos recusa (principalmente no Windows)."""
    limpo = re.sub(r'[<>:"/\\|?*]', "-", nome)
    limpo = re.sub(r"\s+", " ", limpo).strip(" .")
    return limpo[:150] or "audio"
