# -*- mode: python ; coding: utf-8 -*-
"""Receita do PyInstaller pro BaixaFacil.

O ponto critico deste arquivo e o `binaries`: e aqui que o ffmpeg e o ffprobe
entram DENTRO do app. Sem isso o usuario cai naquele fluxo antigo de
"instale o ffmpeg pelo Homebrew", que era justamente o que a gente veio matar.

O yt-dlp NAO aparece aqui como binario de proposito: ele agora e importado como
biblioteca (`import yt_dlp`), entao o PyInstaller o congela junto do resto do
codigo Python. Era exatamente o oposto disso que quebrava a versao antiga, que
empacotava um script com shebang apontando pro venv da maquina do Leo.
"""
import os
import platform

RAIZ = os.path.abspath(os.getcwd())


def plataforma():
    if platform.system() == "Darwin":
        return "mac-arm64" if platform.machine() == "arm64" else "mac-x64"
    if platform.system() == "Windows":
        return "win-x64"
    return "linux-x64"


PLAT = plataforma()
PASTA_BIN = os.path.join(RAIZ, "recursos", "bin", PLAT)
SUFIXO = ".exe" if platform.system() == "Windows" else ""

binarios = []
for nome in ("ffmpeg", "ffprobe"):
    caminho = os.path.join(PASTA_BIN, nome + SUFIXO)
    if not os.path.isfile(caminho):
        raise SystemExit(
            f"\nERRO: {caminho} nao existe.\n"
            f"Rode antes:  python3 scripts/baixar_ffmpeg.py\n"
        )
    # Destino "recursos/bin/<plat>" espelha o layout do repo, que e o primeiro
    # lugar onde baixafacil/binarios.py procura.
    binarios.append((caminho, os.path.join("recursos", "bin", PLAT)))

dados = [
    (os.path.join(RAIZ, "recursos", "flowcore-horizontal.png"), "recursos"),
]

a = Analysis(
    ["main.py"],
    pathex=[RAIZ],
    binaries=binarios,
    datas=dados,
    # yt_dlp carrega os extratores por reflexao; sem isto o PyInstaller
    # descartaria a maior parte dos sites suportados.
    hiddenimports=[
        "yt_dlp",
        "yt_dlp.extractor",
        "yt_dlp.extractor.lazy_extractors",
        "yt_dlp.compat",
        "yt_dlp.utils",
        "yt_dlp.postprocessor",
        "customtkinter",
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        "sqlite3",          # cookiesfrombrowser le o banco do navegador
    ],
    hookspath=[],
    runtime_hooks=[],
    # mutagem/secretstorage nao sao usados e so incham o bundle.
    excludes=["numpy", "matplotlib", "pytest", "tkinter.test"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BaixaFacil",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(RAIZ, "icon.ico") if platform.system() == "Windows" else None,
)

col = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="BaixaFacil",
)

if platform.system() == "Darwin":
    app = BUNDLE(
        col,
        name="BaixaFacil.app",
        icon=os.path.join(RAIZ, "icon.icns"),
        bundle_identifier="com.flowcore.baixafacil",
        info_plist={
            "CFBundleName": "BaixaFacil",
            "CFBundleDisplayName": "BaixaFácil",
            "CFBundleShortVersionString": "2.0.0",
            "CFBundleVersion": "2.0.0",
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "FlowCore | Leonardo Assis | 2026",
            # Sem isto o macOS mostra o app no Dock com nome errado em pt-BR.
            "CFBundleDevelopmentRegion": "pt_BR",
        },
    )
