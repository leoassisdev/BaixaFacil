#!/usr/bin/env python3
"""Baixa ffmpeg e ffprobe estaticos e guarda em recursos/bin/<plataforma>/.

POR QUE ISTO EXISTE
-------------------
A versao antiga do BaixaFacil nao empacotava ffmpeg. Ela mandava o usuario
rodar `brew install ffmpeg` (e no Windows, nada). Resultado: quem instalava o
app nao conseguia baixar audio nem juntar video, e via erro de biblioteca.

Regra do Leo: ao instalar, o app ja tem que trazer TUDO. Ninguem deve abrir
terminal pra usar o BaixaFacil.

Fonte: github.com/eugeneware/ffmpeg-static, que publica binarios estaticos
(sem dependencia de biblioteca do sistema) pras 3 plataformas que a gente
distribui. Sao builds GPL do ffmpeg; a licenca vai junto em recursos/bin/.

Uso:
    python3 scripts/baixar_ffmpeg.py             # so a plataforma atual
    python3 scripts/baixar_ffmpeg.py --todas     # as 3, pra buildar tudo
"""
import argparse
import gzip
import os
import platform
import shutil
import sys
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "recursos", "bin")

API = "https://api.github.com/repos/eugeneware/ffmpeg-static/releases/latest"

# nome interno -> sufixo dos assets no release
PLATAFORMAS = {
    "mac-arm64": "darwin-arm64",
    "mac-x64": "darwin-x64",
    "win-x64": "win32-x64",
}

BINARIOS = ("ffmpeg", "ffprobe")


def plataforma_atual() -> str:
    sistema = platform.system()
    if sistema == "Darwin":
        return "mac-arm64" if platform.machine() == "arm64" else "mac-x64"
    if sistema == "Windows":
        return "win-x64"
    raise SystemExit(f"Sem build empacotado pra {sistema}. Use --todas ou instale o ffmpeg no sistema.")


def assets_do_release() -> dict:
    with urllib.request.urlopen(API, timeout=60) as r:
        import json
        dados = json.load(r)
    print(f"  release ffmpeg-static: {dados['tag_name']}")
    return {a["name"]: a["browser_download_url"] for a in dados["assets"]}


def baixar(url: str, destino: str, rotulo: str) -> None:
    """Baixa e descomprime o .gz direto pro destino, mostrando o progresso."""
    with urllib.request.urlopen(url, timeout=300) as r:
        total = int(r.headers.get("Content-Length") or 0)
        lido = 0
        bruto = bytearray()
        while True:
            pedaco = r.read(256 * 1024)
            if not pedaco:
                break
            bruto += pedaco
            lido += len(pedaco)
            if total:
                pct = lido * 100 // total
                print(f"\r    {rotulo}: {pct:3d}%  ({lido/1048576:.1f}/{total/1048576:.1f} MB)", end="", flush=True)
    print()
    dados = gzip.decompress(bytes(bruto))
    with open(destino, "wb") as f:
        f.write(dados)
    os.chmod(destino, 0o755)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--todas", action="store_true", help="baixa as 3 plataformas")
    ap.add_argument("--forcar", action="store_true", help="rebaixa mesmo se ja existir")
    args = ap.parse_args()

    alvos = list(PLATAFORMAS) if args.todas else [plataforma_atual()]
    print(f"Baixando ffmpeg/ffprobe para: {', '.join(alvos)}")
    assets = assets_do_release()

    for alvo in alvos:
        sufixo = PLATAFORMAS[alvo]
        pasta = os.path.join(DESTINO, alvo)
        os.makedirs(pasta, exist_ok=True)
        print(f"\n  [{alvo}]")

        for binario in BINARIOS:
            ext = ".exe" if alvo.startswith("win") else ""
            saida = os.path.join(pasta, binario + ext)
            if os.path.exists(saida) and not args.forcar:
                print(f"    {binario}: ja existe ({os.path.getsize(saida)/1048576:.1f} MB), pulando")
                continue
            nome_asset = f"{binario}-{sufixo}.gz"
            url = assets.get(nome_asset)
            if not url:
                print(f"    ERRO: asset {nome_asset} nao existe no release")
                return 1
            baixar(url, saida, binario)

        # A licenca precisa viajar junto com o binario (ffmpeg estatico e GPL).
        licenca = os.path.join(pasta, "LICENSE-ffmpeg.txt")
        if not os.path.exists(licenca):
            url_lic = assets.get(f"{sufixo}.LICENSE")
            if url_lic:
                with urllib.request.urlopen(url_lic, timeout=120) as r, open(licenca, "wb") as f:
                    f.write(r.read())
                print("    LICENSE-ffmpeg.txt salvo")

    print("\nPronto. Conferindo:")
    for alvo in alvos:
        pasta = os.path.join(DESTINO, alvo)
        for nome in sorted(os.listdir(pasta)):
            caminho = os.path.join(pasta, nome)
            print(f"  {alvo}/{nome}  {os.path.getsize(caminho)/1048576:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
