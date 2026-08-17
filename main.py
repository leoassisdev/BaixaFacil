#!/usr/bin/env python3
"""BaixaFacil, o baixador de midia da FlowCore.

Cole o link, escolha audio ou video, e baixe. YouTube, Spotify, Facebook,
Instagram, TikTok, SoundCloud e mais de mil sites.

Tudo que o app precisa (yt-dlp e ffmpeg) viaja DENTRO dele. O usuario nunca
abre terminal nem instala nada. Ver baixafacil/binarios.py pro historico do
bug que motivou isso.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import webbrowser

import customtkinter as ctk
from tkinter import filedialog, messagebox

from baixafacil import __version__, atualizacao
from baixafacil.binarios import Ambiente
from baixafacil.motor import (
    ErroDownload, Motor, NAVEGADORES, SITES_SUPORTADOS, precisa_de_login,
)

# Paleta da marca (mesma do site e do Space Scanner).
CIANO = "#00D4FF"
VERMELHO = "#FF1744"
TEXTO = "#EAEAFF"
CINZA = "#8A90A8"
VERDE = "#2FA572"
FUNDO_CARD = "#16181F"

WHATSAPP = "https://wa.me/5511924481753?text=" + \
    "Ol%C3%A1!%20Vim%20pelo%20BaixaF%C3%A1cil%20e%20queria%20falar%20com%20voc%C3%AAs."
GITHUB = "https://github.com/leoassisdev"
LINKEDIN = "https://www.linkedin.com/in/flowcoresolucoes/"
EMAIL = "mailto:contato@flowcoresolucoes.com?subject=Contato%20via%20BaixaF%C3%A1cil"
SITE = "https://flowcoresolucoes.com/"


def recurso(*partes: str) -> str:
    """Caminho de um arquivo de recursos, no bundle ou rodando do codigo."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "recursos", *partes)


class BaixaFacil(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("BaixaFácil")
        self.geometry("780x760")
        self.minsize(700, 700)

        self.ambiente = Ambiente()
        self.motor = Motor(self.ambiente)
        self.baixando = False
        self.versao_nova: atualizacao.Versao | None = None

        self._montar()
        self._checar_dependencias()
        threading.Thread(target=self._checar_atualizacao, daemon=True).start()

    # ── Montagem da tela ────────────────────────────────────────────────

    def _montar(self) -> None:
        self._faixa_marca()
        self._cabecalho()
        self._abas()
        self._status()
        self._rodape()

    def _faixa_marca(self) -> None:
        """Logo horizontal oficial de ponta a ponta, igual ao Space Scanner."""
        faixa = ctk.CTkFrame(self, fg_color="#0D0E13", corner_radius=0, height=54)
        faixa.pack(fill="x")
        faixa.pack_propagate(False)

        caminho = recurso("flowcore-horizontal.png")
        if os.path.isfile(caminho):
            try:
                from PIL import Image
                img = Image.open(caminho)
                altura = 26
                largura = round(img.width * altura / img.height)
                self._logo = ctk.CTkImage(light_image=img, dark_image=img,
                                          size=(largura, altura))
                ctk.CTkLabel(faixa, image=self._logo, text="").pack(expand=True)
                return
            except Exception:
                pass  # cai no texto abaixo

        # Reserva textual: nunca deixar a faixa vazia se a imagem faltar.
        alt = ctk.CTkFrame(faixa, fg_color="transparent")
        alt.pack(expand=True)
        ctk.CTkLabel(alt, text="FLOW", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=CIANO).pack(side="left")
        ctk.CTkLabel(alt, text="CORE", font=ctk.CTkFont(size=17, weight="bold"),
                     text_color=TEXTO).pack(side="left")

    def _cabecalho(self) -> None:
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=28, pady=(18, 0))

        nome = ctk.CTkFrame(topo, fg_color="transparent")
        nome.pack(anchor="w")
        ctk.CTkLabel(nome, text="Baixa", font=ctk.CTkFont(size=30, weight="bold"),
                     text_color=VERMELHO).pack(side="left")
        ctk.CTkLabel(nome, text="Fácil", font=ctk.CTkFont(size=30, weight="bold"),
                     text_color=TEXTO).pack(side="left")
        ctk.CTkLabel(nome, text=f"  v{__version__}", font=ctk.CTkFont(size=12),
                     text_color=CINZA).pack(side="left", pady=(10, 0))

        ctk.CTkLabel(
            topo,
            text="Cole o link e baixe. " + ", ".join(SITES_SUPORTADOS[:6]) + " e mais.",
            font=ctk.CTkFont(size=13), text_color=CINZA,
        ).pack(anchor="w", pady=(2, 0))

    def _abas(self) -> None:
        self.abas = ctk.CTkTabview(self, height=420)
        self.abas.pack(fill="both", expand=True, padx=28, pady=(14, 8))
        self.campos: dict[str, dict] = {}
        for rotulo, modo in [("Áudio", "audio"), ("Vídeo", "video"), ("Playlist", "playlist")]:
            self.campos[modo] = self._montar_aba(self.abas.add(rotulo), modo)

    def _montar_aba(self, pai, modo: str) -> dict:
        caixa = ctk.CTkFrame(pai, fg_color="transparent")
        caixa.pack(fill="both", expand=True, padx=12, pady=10)

        prompts = {
            "audio": "Cole o link da música ou do vídeo (sai em MP3):",
            "video": "Cole o link do vídeo (sai em MP4):",
            "playlist": "Cole o link da playlist, álbum ou canal:",
        }
        ctk.CTkLabel(caixa, text=prompts[modo],
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(0, 6))

        exemplos = {
            "audio": "https://youtube.com/...  ou  https://open.spotify.com/track/...",
            "video": "https://youtube.com/...  ou  https://facebook.com/...",
            "playlist": "https://youtube.com/playlist?list=...  ou  Spotify album/playlist",
        }
        url = ctk.CTkEntry(caixa, placeholder_text=exemplos[modo], height=42,
                           font=ctk.CTkFont(size=13))
        url.pack(fill="x", pady=(0, 14))
        url.bind("<Return>", lambda _e, m=modo: self._clicou_baixar(m))

        formato = None
        if modo == "playlist":
            ctk.CTkLabel(caixa, text="Formato:",
                         font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(0, 4))
            formato = ctk.StringVar(value="video")
            linha = ctk.CTkFrame(caixa, fg_color="transparent")
            linha.pack(fill="x", pady=(0, 14))
            for texto, valor in [("Vídeo (MP4)", "video"), ("Áudio (MP3)", "audio")]:
                ctk.CTkRadioButton(linha, text=texto, variable=formato, value=valor,
                                   font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 26))

        ctk.CTkLabel(caixa, text="Qualidade:",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(0, 4))
        qualidade = ctk.StringVar(value="Alta")
        linha_q = ctk.CTkFrame(caixa, fg_color="transparent")
        linha_q.pack(fill="x", pady=(0, 14))
        for q in ("Alta", "Normal", "Baixa"):
            ctk.CTkRadioButton(linha_q, text=q, variable=qualidade, value=q,
                               font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 26))

        # Login do navegador: so o Instagram e o Facebook restrito precisam.
        login = ctk.BooleanVar(value=False)
        navegador = ctk.StringVar(value=_navegador_padrao())
        caixa_login = ctk.CTkFrame(caixa, fg_color=FUNDO_CARD, corner_radius=10)
        caixa_login.pack(fill="x", pady=(0, 14))

        linha_l = ctk.CTkFrame(caixa_login, fg_color="transparent")
        linha_l.pack(fill="x", padx=14, pady=(11, 2))
        ctk.CTkCheckBox(
            linha_l, text="Usar meu login do navegador", variable=login,
            font=ctk.CTkFont(size=13),
        ).pack(side="left")
        ctk.CTkOptionMenu(linha_l, variable=navegador, values=list(NAVEGADORES),
                          width=110, height=28,
                          font=ctk.CTkFont(size=12)).pack(side="left", padx=(12, 0))
        ctk.CTkLabel(
            caixa_login,
            text="Marque só pra Instagram e conteúdo privado. Seus dados não saem do computador.",
            font=ctk.CTkFont(size=11), text_color=CINZA, wraplength=600, justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 11))

        botao = ctk.CTkButton(
            caixa, text="Escolher pasta e baixar", height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=CIANO, text_color="#04060B", hover_color="#33DDFF",
            command=lambda m=modo: self._clicou_baixar(m),
        )
        botao.pack(fill="x")

        return {"url": url, "qualidade": qualidade, "formato": formato,
                "login": login, "navegador": navegador, "botao": botao}

    def _status(self) -> None:
        self.rotulo_status = ctk.CTkLabel(self, text="Pronto para baixar",
                                          font=ctk.CTkFont(size=13), text_color=CINZA)
        self.rotulo_status.pack(anchor="w", padx=30, pady=(0, 4))

        self.barra = ctk.CTkProgressBar(self, height=10, progress_color=CIANO)
        self.barra.pack(fill="x", padx=30, pady=(0, 12))
        self.barra.set(0)

    def _rodape(self) -> None:
        pe = ctk.CTkFrame(self, fg_color="transparent")
        pe.pack(fill="x", padx=28, pady=(0, 16))

        ctk.CTkLabel(pe, text="FLOW", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=CIANO).pack(side="left")
        ctk.CTkLabel(pe, text="CORE", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXTO).pack(side="left")
        ctk.CTkLabel(pe, text="  por Leonardo Assis, 2026",
                     font=ctk.CTkFont(size=11), text_color="#6C7288").pack(side="left")

        # Botoes sociais no canto inferior direito, mesmo padrao do Space Scanner.
        for texto, destino, cor in [
            ("Email", EMAIL, CIANO),
            ("in", LINKEDIN, "#0A66C2"),
            ("GitHub", GITHUB, "#8B93A7"),
            ("WhatsApp", WHATSAPP, "#25D366"),
        ]:
            ctk.CTkButton(
                pe, text=texto, width=64, height=26, corner_radius=13,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="transparent", border_width=1, border_color="#2A2D3A",
                text_color=cor, hover_color="#20232C",
                command=lambda d=destino: webbrowser.open(d),
            ).pack(side="right", padx=(6, 0))

        ctk.CTkLabel(pe, text="Site", font=ctk.CTkFont(size=11, underline=True),
                     text_color=CIANO, cursor="pointinghand").pack(side="right", padx=(6, 10))
        pe.winfo_children()[-1].bind("<Button-1>", lambda _e: webbrowser.open(SITE))

    # ── Dependencias ────────────────────────────────────────────────────

    def _checar_dependencias(self) -> None:
        """Se o ffmpeg nao veio junto, avisa uma vez e segue.

        A versao antiga travava aqui pedindo `brew install ffmpeg`. Agora o
        binario e empacotado, entao cair neste aviso significa bundle quebrado,
        e o texto tem que dizer isso, nao mandar o usuario pro terminal.
        """
        if self.ambiente.ffmpeg_ok:
            return
        messagebox.showwarning(
            "Instalação incompleta",
            "O conversor de áudio e vídeo não veio junto com este BaixaFácil.\n\n"
            "Baixe o app de novo pela loja da FlowCore:\n"
            "flowcoresolucoes.com/loja/baixa-facil\n\n"
            "Você ainda consegue baixar vídeo, mas converter pra MP3 não vai funcionar.",
        )

    # ── Atualizacao ─────────────────────────────────────────────────────

    def _checar_atualizacao(self) -> None:
        versao = atualizacao.procurar()
        if versao:
            self.versao_nova = versao
            self.after(0, self._oferecer_atualizacao)

    def _oferecer_atualizacao(self) -> None:
        v = self.versao_nova
        if not v:
            return
        quer = messagebox.askyesno(
            "Nova versão disponível",
            f"Saiu a versão {v.numero} do BaixaFácil "
            f"(você está na {__version__}).\n\n"
            f"{(v.notas or 'Correções e melhorias.')[:300]}\n\n"
            "Baixar e instalar agora?",
        )
        if quer:
            self._baixar_atualizacao(v)

    def _baixar_atualizacao(self, versao: atualizacao.Versao) -> None:
        janela = ctk.CTkToplevel(self)
        janela.title("Atualizando")
        janela.geometry("420x170")
        janela.resizable(False, False)
        janela.grab_set()

        ctk.CTkLabel(janela, text=f"Baixando a versão {versao.numero}",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(24, 6))
        detalhe = ctk.CTkLabel(janela, text="Começando...", font=ctk.CTkFont(size=12),
                               text_color=CINZA)
        detalhe.pack()
        barra = ctk.CTkProgressBar(janela, width=350, progress_color=CIANO)
        barra.pack(pady=16)
        barra.set(0)

        def progresso(pct, lido, total):
            self.after(0, lambda: (
                barra.set(pct / 100),
                detalhe.configure(text=f"{lido/1048576:.1f} MB de {total/1048576:.1f} MB"),
            ))

        def rodar():
            caminho = atualizacao.baixar(versao, progresso)
            self.after(0, lambda: self._fim_atualizacao(janela, caminho))

        threading.Thread(target=rodar, daemon=True).start()

    def _fim_atualizacao(self, janela, caminho: str | None) -> None:
        janela.destroy()
        if not caminho:
            messagebox.showerror("Atualização", "Não consegui baixar a atualização agora. "
                                                "Tente mais tarde.")
            return
        messagebox.showinfo("Pronto pra instalar",
                            "Vou abrir o instalador. Feche o BaixaFácil, conclua a "
                            "instalação e abra o app de novo.")
        atualizacao.instalar(caminho)

    # ── Download ────────────────────────────────────────────────────────

    def _clicou_baixar(self, modo: str) -> None:
        if self.baixando:
            messagebox.showwarning("Calma lá", "Já tem um download rolando.")
            return

        campos = self.campos[modo]
        url = campos["url"].get().strip()
        if not url:
            messagebox.showwarning("Falta o link", "Cole um link primeiro.")
            campos["url"].focus()
            return

        navegador = campos["navegador"].get() if campos["login"].get() else ""
        if precisa_de_login(url) and not navegador:
            seguir = messagebox.askyesno(
                "Esse site costuma exigir login",
                "Instagram e conteúdo privado do Facebook só entregam a mídia pra quem "
                "está logado.\n\nQuer tentar assim mesmo?\n\n"
                "(Se der erro, marque 'Usar meu login do navegador' e tente de novo.)",
            )
            if not seguir:
                return

        destino = filedialog.askdirectory(title="Onde salvar?")
        if not destino:
            return

        somente_audio = modo == "audio"
        playlist = modo == "playlist"
        if playlist and campos["formato"]:
            somente_audio = campos["formato"].get() == "audio"

        self.baixando = True
        campos["botao"].configure(state="disabled", text="Baixando...")
        self.barra.set(0)
        self._dizer("Preparando...", CIANO)

        threading.Thread(
            target=self._rodar_download,
            args=(url, destino, campos["qualidade"].get(), somente_audio,
                  playlist, navegador, modo),
            daemon=True,
        ).start()

    def _rodar_download(self, url, destino, qualidade, somente_audio,
                        playlist, navegador, modo) -> None:
        try:
            pedido = self.motor.preparar(
                url=url, destino=destino, qualidade=qualidade,
                somente_audio=somente_audio, playlist=playlist, navegador=navegador,
            )
            if pedido.rotulo_origem:
                total = len(pedido.musicas_spotify)
                self.after(0, self._dizer,
                           f"{pedido.rotulo_origem} ({total} música{'s' if total > 1 else ''})",
                           CIANO)

            salvos = self.motor.baixar(pedido, self._veio_progresso)
            self.after(0, self._deu_certo, destino, salvos, modo)

        except ErroDownload as exc:
            self.after(0, self._deu_errado, str(exc), modo)
        except Exception as exc:
            self.after(0, self._deu_errado, f"Erro inesperado: {exc}", modo)

    def _veio_progresso(self, p) -> None:
        def pintar():
            self.barra.set(p.porcentagem / 100)
            if p.etapa == "convertendo":
                self._dizer("Convertendo o arquivo...", CIANO)
                return
            partes = []
            if p.total_itens > 1:
                partes.append(f"[{p.item_atual}/{p.total_itens}]")
            if p.titulo:
                partes.append(p.titulo[:52])
            if p.velocidade:
                partes.append(p.velocidade)
            if p.faltando:
                partes.append(f"faltam {p.faltando}")
            self._dizer(" · ".join(partes) or "Baixando...", CIANO)
        self.after(0, pintar)

    def _deu_certo(self, destino: str, salvos: int, modo: str) -> None:
        self._liberar(modo)
        self.barra.set(1.0)
        plural = "arquivos" if salvos > 1 else "arquivo"
        self._dizer(f"Pronto! {salvos} {plural} em {destino}", VERDE)
        _abrir_pasta(destino)
        messagebox.showinfo("Concluído",
                            f"{salvos} {plural} salvo{'s' if salvos > 1 else ''} em:\n\n{destino}")
        self.barra.set(0)
        self._dizer("Pronto para baixar", CINZA)

    def _deu_errado(self, mensagem: str, modo: str) -> None:
        self._liberar(modo)
        self.barra.set(0)
        self._dizer("Não deu certo", VERMELHO)
        messagebox.showerror("Não consegui baixar", mensagem)
        self._dizer("Pronto para baixar", CINZA)

    def _liberar(self, modo: str) -> None:
        self.baixando = False
        self.campos[modo]["botao"].configure(state="normal", text="Escolher pasta e baixar")

    def _dizer(self, texto: str, cor: str = CINZA) -> None:
        limite = 92
        curto = texto if len(texto) <= limite else texto[:limite] + "..."
        self.rotulo_status.configure(text=curto, text_color=cor)


def _navegador_padrao() -> str:
    return "safari" if platform.system() == "Darwin" else "chrome"


def _abrir_pasta(caminho: str) -> None:
    sistema = platform.system()
    try:
        if sistema == "Darwin":
            subprocess.run(["open", caminho], check=False)
        elif sistema == "Windows":
            os.startfile(caminho)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", caminho], check=False)
    except Exception:
        pass


def _diagnostico() -> int:
    """Modo texto: prova que as dependências vieram dentro do app.

    Existe por dois motivos:
      1. suporte, o usuário roda e me manda a saída em vez de descrever o erro;
      2. teste, o build automatizado chama isto DENTRO do app empacotado e
         baixa de verdade. É o que garante que o bug do "yt-dlp não encontrado"
         não volta sem alguém perceber.
    """
    import tempfile

    ambiente = Ambiente()
    print("BaixaFácil " + __version__)
    print(ambiente.diagnostico())
    print(f"empacotado: {bool(getattr(sys, 'frozen', False))}")

    if "--baixar-teste" not in sys.argv:
        return 0 if ambiente.ffmpeg_ok else 1

    if not ambiente.ffmpeg_ok:
        print("\nFALHA: sem ffmpeg dentro do app.")
        return 1

    pasta = tempfile.mkdtemp(prefix="bf-diag-")
    print(f"\nbaixando 1 áudio de teste em {pasta}")
    try:
        motor = Motor(ambiente)
        pedido = motor.preparar(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            destino=pasta, qualidade="Baixa",
            somente_audio=True, playlist=False,
        )
        motor.baixar(pedido, lambda _p: None)
    except Exception as exc:
        print(f"FALHA: {exc}")
        return 1

    arquivos = [f for f in os.listdir(pasta) if f.endswith(".mp3")]
    if not arquivos:
        print("FALHA: terminou sem gerar MP3.")
        return 1
    caminho = os.path.join(pasta, arquivos[0])
    print(f"OK: {arquivos[0]}  {os.path.getsize(caminho)/1048576:.1f} MB")
    return 0


if __name__ == "__main__":
    if "--diagnostico" in sys.argv:
        sys.exit(_diagnostico())
    BaixaFacil().mainloop()
