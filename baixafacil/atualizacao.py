"""Atualizacao automatica dentro do app (padrao FlowCore).

O usuario nunca precisa voltar no site pra pegar versao nova: o app checa
sozinho, avisa num popup com barra de progresso, baixa o instalador e abre.

Diferenca pro Space Scanner (Electron): aqui nao da pra trocar os arquivos do
app com ele rodando, entao o fluxo termina abrindo o instalador (.dmg no mac,
.exe no Windows) e pedindo pro usuario confirmar. E o mesmo padrao do TurboDrive.

Fonte das versoes: releases do GitHub, consultadas pelo dominio da FlowCore
quando disponivel, com o GitHub como reserva.
"""
from __future__ import annotations

import json
import os
import platform
import re
import ssl
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from . import __version__

API_RELEASE = "https://api.github.com/repos/leoassisdev/BaixaFacil/releases/latest"
PAGINA_PRODUTO = "https://flowcoresolucoes.com/loja/baixa-facil"

CABECALHOS = {"User-Agent": f"BaixaFacil/{__version__}", "Accept": "application/vnd.github+json"}


@dataclass
class Versao:
    numero: str
    notas: str
    url_instalador: str
    tamanho: int


def _partes(v: str) -> tuple[int, ...]:
    """'2.1.10' -> (2, 1, 10). Compara numero por numero, nao alfabeticamente:
    senao '2.10' sairia como menor que '2.9'."""
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


def eh_mais_nova(remota: str, local: str = __version__) -> bool:
    return _partes(remota) > _partes(local)


def _sufixo_da_plataforma() -> tuple[str, ...]:
    """Como reconhecer o instalador desta maquina no release."""
    sistema = platform.system()
    if sistema == "Darwin":
        return ("-arm64.dmg",) if platform.machine() == "arm64" else ("-x64.dmg", "-intel.dmg")
    if sistema == "Windows":
        return ("-setup-x64.exe", ".exe")
    return ()


def procurar() -> Versao | None:
    """Consulta o release mais recente. Devolve None se ja estamos atualizados."""
    try:
        pedido = urllib.request.Request(API_RELEASE, headers=CABECALHOS)
        contexto = ssl.create_default_context()
        with urllib.request.urlopen(pedido, timeout=20, context=contexto) as r:
            dados = json.load(r)
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        # Sem internet ou GitHub fora: nao e erro que mereca incomodar o usuario.
        return None

    tag = (dados.get("tag_name") or "").lstrip("vV")
    if not tag or not eh_mais_nova(tag):
        return None

    sufixos = _sufixo_da_plataforma()
    for sufixo in sufixos:
        for asset in dados.get("assets", []):
            nome = asset.get("name", "")
            if nome.endswith(sufixo):
                return Versao(
                    numero=tag,
                    notas=(dados.get("body") or "").strip()[:1200],
                    url_instalador=asset.get("browser_download_url", ""),
                    tamanho=asset.get("size", 0),
                )
    return None


def baixar(versao: Versao, aoProgresso: Callable[[float, int, int], None],
           cancelado: Callable[[], bool] | None = None) -> str | None:
    """Baixa o instalador pra pasta temporaria. Devolve o caminho, ou None."""
    destino = os.path.join(tempfile.gettempdir(), os.path.basename(versao.url_instalador))
    try:
        pedido = urllib.request.Request(versao.url_instalador, headers=CABECALHOS)
        with urllib.request.urlopen(pedido, timeout=120) as r, open(destino, "wb") as f:
            total = int(r.headers.get("Content-Length") or versao.tamanho or 0)
            lido = 0
            while True:
                if cancelado and cancelado():
                    return None
                pedaco = r.read(256 * 1024)
                if not pedaco:
                    break
                f.write(pedaco)
                lido += len(pedaco)
                aoProgresso((lido / total * 100) if total else 0.0, lido, total)
        return destino
    except (urllib.error.URLError, OSError):
        # Deixa o meio-download pra tras de proposito seria pior: limpa.
        try:
            os.remove(destino)
        except OSError:
            pass
        return None


def instalar(caminho: str) -> None:
    """Abre o instalador baixado. O usuario conclui e reabre o app."""
    import subprocess
    if platform.system() == "Darwin":
        subprocess.run(["open", caminho], check=False)
    elif platform.system() == "Windows":
        os.startfile(caminho)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", caminho], check=False)
