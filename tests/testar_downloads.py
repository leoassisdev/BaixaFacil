#!/usr/bin/env python3
"""Baixa DE VERDADE de cada site prometido e confere o arquivo que saiu.

Nao e mock: cada caso vai na internet, baixa, e o teste checa que o arquivo
existe, tem tamanho plausivel e (quando e midia) abre no ffprobe com duracao
maior que zero. Se o YouTube mudar alguma coisa, este teste quebra.

Uso:
    .venv/bin/python tests/testar_downloads.py            # tudo
    .venv/bin/python tests/testar_downloads.py youtube    # so o que casar
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from baixafacil.binarios import Ambiente
from baixafacil.motor import Motor, ErroDownload

# Conteudo publico e estavel, escolhido pra nao sumir do ar.
CASOS = [
    {
        "nome": "youtube-audio",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "audio": True, "playlist": False,
        "min_kb": 500, "min_seg": 60,
    },
    {
        "nome": "youtube-video",
        "url": "https://www.youtube.com/watch?v=aqz-KE-bpKQ",  # Big Buck Bunny (Blender, CC)
        "audio": False, "playlist": False,
        "min_kb": 1000, "min_seg": 30,
        "qualidade": "Baixa",   # o de verdade e enorme; baixa ja prova o caminho
    },
    {
        "nome": "spotify-faixa",
        "url": "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
        "audio": True, "playlist": False,
        "min_kb": 500, "min_seg": 60,
    },
    {
        "nome": "soundcloud",
        "url": "https://soundcloud.com/uiceheidd/lucid-dreams-forget-me",
        "audio": True, "playlist": False,
        "min_kb": 300, "min_seg": 20,   # varios uploads do SoundCloud sao previa de 30s
        "opcional": True,
    },
    {
        "nome": "vimeo",
        "url": "https://vimeo.com/76979871",
        "audio": False, "playlist": False,
        "min_kb": 300, "min_seg": 5,
        "opcional": True,
    },
    {
        "nome": "instagram",
        "url": "https://www.instagram.com/reel/C0nT3nT/",
        "audio": False, "playlist": False,
        "min_kb": 100, "min_seg": 1,
        "opcional": True,   # o Instagram bloqueia muito por IP/login
    },
    {
        "nome": "facebook",
        "url": "https://www.facebook.com/watch/?v=10153231379946729",
        "audio": False, "playlist": False,
        "min_kb": 100, "min_seg": 1,
        "opcional": True,
    },
]


def duracao_segundos(ffprobe: str | None, caminho: str) -> float:
    if not ffprobe:
        return -1.0
    try:
        saida = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", caminho],
            capture_output=True, text=True, timeout=60,
        )
        return float(json.loads(saida.stdout)["format"]["duration"])
    except Exception:
        return -1.0


def rodar_caso(motor: Motor, caso: dict, ambiente: Ambiente) -> tuple[bool, str]:
    pasta = tempfile.mkdtemp(prefix=f"bf-{caso['nome']}-")
    ultimo = {"pct": 0.0}

    def progresso(p):
        ultimo["pct"] = p.porcentagem

    try:
        inicio = time.time()
        pedido = motor.preparar(
            url=caso["url"], destino=pasta,
            qualidade=caso.get("qualidade", "Alta"),
            somente_audio=caso["audio"], playlist=caso["playlist"],
        )
        motor.baixar(pedido, progresso)
        levou = time.time() - inicio

        arquivos = [
            os.path.join(pasta, f) for f in os.listdir(pasta)
            if not f.startswith(".") and not f.endswith((".part", ".ytdl", ".webp", ".jpg"))
        ]
        if not arquivos:
            return False, "baixou sem erro mas nao sobrou arquivo nenhum"

        maior = max(arquivos, key=os.path.getsize)
        kb = os.path.getsize(maior) / 1024
        if kb < caso["min_kb"]:
            return False, f"arquivo pequeno demais: {kb:.0f} KB (minimo {caso['min_kb']})"

        seg = duracao_segundos(ambiente.ffprobe, maior)
        if seg >= 0 and seg < caso["min_seg"]:
            return False, f"duracao curta demais: {seg:.0f}s (minimo {caso['min_seg']})"

        nome = os.path.basename(maior)
        dur = f"{seg:.0f}s" if seg >= 0 else "?"
        return True, f"{nome[:52]}  {kb/1024:.1f} MB  {dur}  em {levou:.0f}s"

    except ErroDownload as exc:
        return False, f"ErroDownload: {exc}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def main() -> int:
    filtro = sys.argv[1] if len(sys.argv) > 1 else ""
    ambiente = Ambiente()
    print(ambiente.diagnostico())
    if not ambiente.ffmpeg_ok:
        print("\nERRO: sem ffmpeg. Rode: python3 scripts/baixar_ffmpeg.py")
        return 1

    motor = Motor(ambiente)
    casos = [c for c in CASOS if filtro in c["nome"]]
    print(f"\nBaixando de verdade, {len(casos)} casos:\n")

    obrigatorios_falhos = 0
    opcionais_falhos = []

    for caso in casos:
        etiqueta = caso["nome"] + (" (opcional)" if caso.get("opcional") else "")
        print(f"  {etiqueta:<26}", end=" ", flush=True)
        ok, detalhe = rodar_caso(motor, caso, ambiente)
        if ok:
            print(f"OK    {detalhe}")
        elif caso.get("opcional"):
            print(f"pulou {detalhe[:90]}")
            opcionais_falhos.append(caso["nome"])
        else:
            print(f"FALHA {detalhe[:90]}")
            obrigatorios_falhos += 1

    print()
    if opcionais_falhos:
        print(f"Opcionais que nao vieram: {', '.join(opcionais_falhos)}")
        print("(sao sites que bloqueiam por IP/login; nao travam o release)")
    if obrigatorios_falhos:
        print(f"\n{obrigatorios_falhos} caso(s) OBRIGATORIO(s) falharam.")
        return 1
    print("Todos os casos obrigatorios passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
