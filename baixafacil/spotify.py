"""Resolve links do Spotify em consultas de busca.

Como funciona, e por que assim
------------------------------
O yt-dlp nao baixa do Spotify (o audio de la e protegido). O caminho que todo
mundo usa e o mesmo do spotdl: ler os METADADOS publicos do link (nome da
faixa e artista) e depois procurar essa musica numa fonte que o yt-dlp
consegue baixar.

Aqui a leitura dos metadados sai do endpoint de EMBED do proprio Spotify
(open.spotify.com/embed/...), que devolve um JSON publico. Isso evita depender
do spotdl (dependencia pesada) e de credenciais de API, que o usuario teria que
cadastrar. Nada de login, nada de chave.

Suporta faixa, album e playlist.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

# open.spotify.com/track/<id>, /album/<id>, /playlist/<id>, com ou sem /intl-pt/
PADRAO_URL = re.compile(
    r"open\.spotify\.com/(?:intl-[a-z]{2}/)?(track|album|playlist)/([A-Za-z0-9]+)",
    re.I,
)
PADRAO_URI = re.compile(r"spotify:(track|album|playlist):([A-Za-z0-9]+)", re.I)

_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


class ErroSpotify(Exception):
    """Falha ao ler o link do Spotify, com mensagem em portugues pro usuario."""


@dataclass
class Musica:
    titulo: str
    artista: str

    @property
    def busca(self) -> str:
        """Consulta enviada pra busca. Artista primeiro acerta mais."""
        return f"{self.artista} - {self.titulo}".strip(" -")

    @property
    def nome_arquivo(self) -> str:
        return f"{self.artista} - {self.titulo}".strip(" -")


@dataclass
class Resultado:
    tipo: str          # track | album | playlist
    nome: str          # nome da faixa, do album ou da playlist
    musicas: list[Musica]


def eh_spotify(url: str) -> bool:
    return bool(PADRAO_URL.search(url) or PADRAO_URI.search(url))


def _identificar(url: str) -> tuple[str, str]:
    achado = PADRAO_URL.search(url) or PADRAO_URI.search(url)
    if not achado:
        raise ErroSpotify("Esse link do Spotify não parece ser de faixa, álbum ou playlist.")
    return achado.group(1).lower(), achado.group(2)


def _buscar_entidade(tipo: str, ident: str) -> dict:
    endereco = f"https://open.spotify.com/embed/{tipo}/{ident}"
    pedido = urllib.request.Request(endereco, headers=CABECALHOS)
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resposta:
            html = resposta.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ErroSpotify("Esse link do Spotify não existe mais ou é privado.") from exc
        raise ErroSpotify(f"O Spotify respondeu com erro {exc.code}.") from exc
    except OSError as exc:
        raise ErroSpotify("Não consegui falar com o Spotify. Confira sua internet.") from exc

    achado = _NEXT_DATA.search(html)
    if not achado:
        raise ErroSpotify("O Spotify mudou o formato da página. Me avise que eu ajusto.")
    try:
        dados = json.loads(achado.group(1))
        return dados["props"]["pageProps"]["state"]["data"]["entity"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise ErroSpotify("Não consegui ler os dados dessa página do Spotify.") from exc


def resolver(url: str) -> Resultado:
    """Transforma um link do Spotify na lista de musicas a procurar."""
    tipo, ident = _identificar(url)
    entidade = _buscar_entidade(tipo, ident)
    nome = entidade.get("name") or "Spotify"

    if tipo == "track":
        artistas = [a.get("name", "") for a in entidade.get("artists", []) if a.get("name")]
        artista = ", ".join(artistas)
        if not artista:
            # Em algumas respostas o artista so vem no subtitle.
            artista = entidade.get("subtitle", "") or ""
        return Resultado(tipo, nome, [Musica(titulo=nome, artista=artista)])

    # Album e playlist trazem a lista pronta em trackList.
    faixas = entidade.get("trackList") or []
    musicas = [
        Musica(titulo=(f.get("title") or "").strip(), artista=(f.get("subtitle") or "").strip())
        for f in faixas
        if (f.get("title") or "").strip()
    ]
    if not musicas:
        raise ErroSpotify(
            "Esse álbum/playlist não expôs a lista de faixas. "
            "Tente abrir a música individual no Spotify e colar o link dela."
        )
    return Resultado(tipo, nome, musicas)
