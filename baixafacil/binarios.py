"""Descoberta do ffmpeg/ffprobe que viajam DENTRO do app.

O bug que motivou este modulo
-----------------------------
A versao antiga empacotava o `yt-dlp` como script de console do Python, com
shebang apontando pro venv da maquina do Leo:

    #!/Users/leoassis/dev/BaixaFacil/venv/bin/python3.14

Em qualquer outro computador esse interpretador nao existe, o exec falha com
FileNotFoundError e o app mostrava "yt-dlp nao encontrado! Instale com:
pip install yt-dlp". O ffmpeg, esse, nem empacotado era: o app pedia pro
usuario rodar `brew install ffmpeg`.

Como resolvemos
---------------
1. O yt-dlp virou BIBLIOTECA (`import yt_dlp`). O PyInstaller congela o modulo
   junto do app, entao nao ha binario externo, nem shebang, nem PATH.
2. O ffmpeg e o ffprobe sao binarios nativos de verdade, entao continuam sendo
   arquivos: ficam em recursos/bin/<plataforma>/ e sao copiados pro bundle.

A ordem de busca abaixo procura primeiro o que veio no app e so depois olha o
sistema, pra que a experiencia seja identica em maquina limpa.
"""
from __future__ import annotations

import os
import platform
import shutil
import stat
import sys

# Caminhos onde o Homebrew e o Linux costumam deixar binarios. Sao o ULTIMO
# recurso: se cairmos aqui e porque o bundle veio incompleto.
CAMINHOS_SISTEMA = [
    "/opt/homebrew/bin",   # Homebrew em Apple Silicon
    "/usr/local/bin",      # Homebrew em Intel
    "/usr/bin",
    "/bin",
]


def plataforma() -> str:
    """Nome da pasta em recursos/bin/ correspondente a esta maquina."""
    sistema = platform.system()
    if sistema == "Darwin":
        return "mac-arm64" if platform.machine() == "arm64" else "mac-x64"
    if sistema == "Windows":
        return "win-x64"
    return "linux-x64"


def _sufixo() -> str:
    return ".exe" if platform.system() == "Windows" else ""


def _raizes_do_bundle() -> list[str]:
    """Lugares onde o binario pode estar, do app empacotado ao repo em dev."""
    raizes: list[str] = []

    # PyInstaller --onefile descompacta tudo num temporario.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        raizes.append(meipass)

    if getattr(sys, "frozen", False):
        pasta_exe = os.path.dirname(sys.executable)
        raizes.append(pasta_exe)
        # Num .app do macOS, sys.executable fica em Contents/MacOS/.
        # Os recursos ficam em Contents/Resources/ e Contents/Frameworks/.
        contents = os.path.dirname(pasta_exe)
        raizes.append(os.path.join(contents, "Resources"))
        raizes.append(os.path.join(contents, "Frameworks"))
    else:
        # Rodando do codigo-fonte.
        raizes.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    return raizes


def localizar(nome: str) -> str | None:
    """Acha `ffmpeg` ou `ffprobe`. Devolve None se nao existir em lugar nenhum."""
    arquivo = nome + _sufixo()
    plat = plataforma()

    for raiz in _raizes_do_bundle():
        candidatos = [
            # Layout vendorizado do repo e do bundle.
            os.path.join(raiz, "recursos", "bin", plat, arquivo),
            # PyInstaller costuma achatar os add-data na raiz.
            os.path.join(raiz, "bin", arquivo),
            os.path.join(raiz, arquivo),
        ]
        for caminho in candidatos:
            if os.path.isfile(caminho):
                _garantir_executavel(caminho)
                return caminho

    # Ultimo recurso: o que estiver no sistema do usuario.
    do_sistema = shutil.which(nome)
    if do_sistema:
        return do_sistema
    for pasta in CAMINHOS_SISTEMA:
        caminho = os.path.join(pasta, arquivo)
        if os.path.isfile(caminho):
            return caminho
    return None


def _garantir_executavel(caminho: str) -> None:
    """O bit +x se perde ao copiar pra exFAT, zip e Google Drive.

    Sem isto o binario existe mas nao roda, e o erro que aparece ("Permission
    denied") nao ajuda ninguem a entender o que houve.
    """
    try:
        modo = os.stat(caminho).st_mode
        if not modo & stat.S_IXUSR:
            os.chmod(caminho, modo | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


class Ambiente:
    """Estado das dependencias, resolvido uma vez no boot do app."""

    def __init__(self) -> None:
        self.ffmpeg = localizar("ffmpeg")
        self.ffprobe = localizar("ffprobe")

    @property
    def ffmpeg_ok(self) -> bool:
        return bool(self.ffmpeg)

    @property
    def pasta_ffmpeg(self) -> str | None:
        """O yt-dlp quer a PASTA, nao o caminho do binario."""
        return os.path.dirname(self.ffmpeg) if self.ffmpeg else None

    def diagnostico(self) -> str:
        """Texto curto pro rodape/tela de ajuda, util em suporte."""
        linhas = [f"plataforma: {plataforma()}"]
        linhas.append(f"ffmpeg:  {self.ffmpeg or 'NAO ENCONTRADO'}")
        linhas.append(f"ffprobe: {self.ffprobe or 'NAO ENCONTRADO'}")
        try:
            import yt_dlp
            linhas.append(f"yt-dlp:  {yt_dlp.version.__version__} (biblioteca embutida)")
        except Exception as exc:
            linhas.append(f"yt-dlp:  FALHOU AO IMPORTAR ({exc})")
        return "\n".join(linhas)
