#!/usr/bin/env python3
"""BaixaFacil - Baixe vídeos e áudios do YouTube com facilidade."""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import subprocess
import threading
import webbrowser
import shutil
import os
import re


QUALITY_AUDIO = {"Alta": "0", "Normal": "5", "Baixa": "9"}
QUALITY_VIDEO = {
    "Alta": "res,vcodec:h264,acodec:aac",
    "Normal": "res:720,vcodec:h264,acodec:aac",
    "Baixa": "res:480,vcodec:h264,acodec:aac",
}


class BaixaFacil(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("BaixaFácil")
        self.geometry("740x600")
        self.resizable(False, False)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.downloading = False
        self.yt_dlp_path = self._find_yt_dlp()

        self._check_dependencies()
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=30, pady=(25, 0))

        title_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        title_frame.pack(anchor="w")

        ctk.CTkLabel(
            title_frame, text="Baixa",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color="#FF1744",
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame, text="Fácil",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color="#EAEAFF",
        ).pack(side="left")

        ctk.CTkLabel(
            hdr, text="Baixe áudios e vídeos do YouTube",
            font=ctk.CTkFont(size=14), text_color="gray",
        ).pack(anchor="w", pady=(2, 0))

        # Tabs
        self.tabview = ctk.CTkTabview(self, width=680, height=370)
        self.tabview.pack(padx=30, pady=(15, 10))

        for label, mode in [("Áudio", "audio"), ("Vídeo", "video"), ("Playlist", "playlist")]:
            tab = self.tabview.add(label)
            self._build_tab(tab, mode)

        # Status + progress
        self.status_label = ctk.CTkLabel(
            self, text="Pronto para baixar",
            font=ctk.CTkFont(size=13), text_color="gray",
        )
        self.status_label.pack(anchor="w", padx=30, pady=(0, 4))

        self.progress = ctk.CTkProgressBar(self, width=680)
        self.progress.pack(padx=30, pady=(0, 15))
        self.progress.set(0)

        # Footer
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=30, pady=(0, 12))

        ctk.CTkLabel(
            footer, text="FLOW",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#00D4FF",
        ).pack(side="left")

        ctk.CTkLabel(
            footer, text="CORE",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#EAEAFF",
        ).pack(side="left")

        ctk.CTkLabel(
            footer, text="  BY LEONARDO ASSIS - 2026",
            font=ctk.CTkFont(size=11),
            text_color="#888888",
        ).pack(side="left")

        link = ctk.CTkLabel(
            footer, text="CONHEÇA NOSSA MARCA",
            font=ctk.CTkFont(size=11, underline=True),
            text_color="#00D4FF", cursor="pointinghand",
        )
        link.pack(side="right")
        link.bind("<Button-1>", lambda e: webbrowser.open("https://flowcoresolucoes.com/"))

    def _build_tab(self, parent, mode):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        # URL input
        prompts = {
            "audio": "Cole o link do áudio aqui:",
            "video": "Cole o link do vídeo aqui:",
            "playlist": "Cole o link da playlist aqui:",
        }
        ctk.CTkLabel(
            frame, text=prompts[mode],
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(0, 6))

        url_entry = ctk.CTkEntry(
            frame, placeholder_text="https://www.youtube.com/watch?v=...",
            height=42, font=ctk.CTkFont(size=14),
        )
        url_entry.pack(fill="x", pady=(0, 18))

        # Playlist format selector
        format_var = None
        if mode == "playlist":
            ctk.CTkLabel(
                frame, text="Formato:",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).pack(anchor="w", pady=(0, 6))

            format_var = ctk.StringVar(value="video")
            fmt_frame = ctk.CTkFrame(frame, fg_color="transparent")
            fmt_frame.pack(fill="x", pady=(0, 18))
            for text, val in [("Vídeo (MP4)", "video"), ("Áudio (MP3)", "audio")]:
                ctk.CTkRadioButton(
                    fmt_frame, text=text, variable=format_var, value=val,
                    font=ctk.CTkFont(size=13),
                ).pack(side="left", padx=(0, 30))

        # Quality selector
        ctk.CTkLabel(
            frame, text="Qualidade:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(0, 6))

        quality_var = ctk.StringVar(value="Alta")
        q_frame = ctk.CTkFrame(frame, fg_color="transparent")
        q_frame.pack(fill="x", pady=(0, 22))
        for q in ("Alta", "Normal", "Baixa"):
            ctk.CTkRadioButton(
                q_frame, text=q, variable=quality_var, value=q,
                font=ctk.CTkFont(size=13),
            ).pack(side="left", padx=(0, 30))

        # Download button
        ctk.CTkButton(
            frame, text="Escolher pasta e baixar",
            height=45, font=ctk.CTkFont(size=15, weight="bold"),
            command=lambda: self._on_download(url_entry, quality_var, mode, format_var),
        ).pack(fill="x")

    # ── Dependency checks ────────────────────────────────────────────────

    def _find_yt_dlp(self):
        venv_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "yt-dlp")
        if os.path.isfile(venv_bin):
            return venv_bin
        sys_bin = shutil.which("yt-dlp")
        return sys_bin or "yt-dlp"

    def _check_dependencies(self):
        if not shutil.which("ffmpeg"):
            messagebox.showwarning(
                "ffmpeg não encontrado",
                "O ffmpeg é necessário para converter áudios e mesclar vídeos.\n\n"
                "Instale com:  brew install ffmpeg",
            )

    # ── Download logic ───────────────────────────────────────────────────

    def _on_download(self, url_entry, quality_var, mode, format_var):
        if self.downloading:
            messagebox.showwarning("Aguarde", "Um download já está em andamento.")
            return

        url = url_entry.get().strip()
        if not url:
            messagebox.showwarning("Atenção", "Cole um link do YouTube primeiro!")
            return

        dest = filedialog.askdirectory(title="Onde deseja salvar o arquivo?")
        if not dest:
            return

        quality = quality_var.get()
        dl_mode = mode
        if mode == "playlist" and format_var:
            dl_mode = f"playlist_{format_var.get()}"

        self.downloading = True
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self._set_status("Baixando... aguarde", "#3B8ED0")

        threading.Thread(
            target=self._run_download,
            args=(url, dest, quality, dl_mode),
            daemon=True,
        ).start()

    def _build_cmd(self, url, dest, quality, mode):
        is_audio = mode in ("audio", "playlist_audio")
        is_playlist = mode.startswith("playlist")

        cmd = [self.yt_dlp_path]

        if is_audio:
            cmd += [
                "-x", "--audio-format", "mp3",
                "--audio-quality", QUALITY_AUDIO[quality],
                "-o", os.path.join(dest, "%(title)s.%(ext)s"),
            ]
        else:
            cmd += [
                "-P", dest,
                "-S", QUALITY_VIDEO[quality],
                "--merge-output-format", "mp4",
            ]

        cmd.append("--yes-playlist" if is_playlist else "--no-playlist")
        cmd.append(url)
        return cmd

    def _run_download(self, url, dest, quality, mode):
        try:
            cmd = self._build_cmd(url, dest, quality, mode)
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )

            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                match = re.search(r"(\d+\.?\d*)%", line)
                if match:
                    self.after(0, self._show_progress, float(match.group(1)), line)
                else:
                    self.after(0, self._set_status, self._truncate(line), "#3B8ED0")

            proc.wait()

            if proc.returncode == 0:
                self.after(0, self._on_success, dest)
            else:
                self.after(0, self._on_error, "Erro no download. Verifique o link e tente novamente.")

        except FileNotFoundError:
            self.after(0, self._on_error, "yt-dlp não encontrado!\nInstale com: pip install yt-dlp")
        except Exception as exc:
            self.after(0, self._on_error, str(exc))

    # ── UI helpers ───────────────────────────────────────────────────────

    def _set_status(self, text, color="gray"):
        self.status_label.configure(text=self._truncate(text), text_color=color)

    def _show_progress(self, pct, text):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(pct / 100)
        self._set_status(self._truncate(text), "#3B8ED0")

    def _on_success(self, dest):
        self.downloading = False
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(1.0)
        self._set_status(f"Concluído! Salvo em: {dest}", "#2FA572")
        subprocess.run(["open", dest])
        messagebox.showinfo("Sucesso!", f"Download concluído!\n\nSalvo em:\n{dest}")
        self.progress.set(0)
        self._set_status("Pronto para baixar")

    def _on_error(self, msg):
        self.downloading = False
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self._set_status("Erro no download", "#E74C3C")
        messagebox.showerror("Erro", msg)

    @staticmethod
    def _truncate(text, maxlen=85):
        return text if len(text) <= maxlen else text[:maxlen] + "..."


if __name__ == "__main__":
    app = BaixaFacil()
    app.mainloop()
