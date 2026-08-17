# BaixaFácil

App de desktop da FlowCore pra baixar áudio e vídeo colando o link. YouTube,
Spotify, Facebook, Instagram, TikTok, SoundCloud e mais de mil sites, em MP3 ou
MP4, inclusive playlists inteiras.

**100% gratuito.** Sem cadastro, sem assinatura, sem anúncio.

Página do produto: <https://flowcoresolucoes.com/loja/baixa-facil>

## O bug que a versão 2.0 matou

Até a 1.x o app chamava o `yt-dlp` como **binário externo**. O que ia dentro do
`.dmg` era o script de console do Python, cujo shebang apontava pra máquina de
quem fez o build:

```
#!/Users/leoassis/dev/BaixaFacil/venv/bin/python3.14
```

Em qualquer outro computador esse interpretador não existe. O `exec` falhava com
`FileNotFoundError` e o usuário via a caixa:

> yt-dlp não encontrado! Instale com: pip install yt-dlp

O `ffmpeg` nem empacotado era: o app mandava o usuário rodar `brew install ffmpeg`.

**Na 2.0:**

- O `yt-dlp` virou **biblioteca** (`import yt_dlp`). O PyInstaller congela o
  módulo junto do app. Não existe binário pra sumir, nem PATH, nem `pip`.
- O `ffmpeg` e o `ffprobe` são binários estáticos de verdade, empacotados em
  `recursos/bin/<plataforma>/` e copiados pro bundle pelo `BaixaFacil.spec`.
- O CI roda o app **já empacotado** e baixa um MP3 de verdade a cada build. Se
  a dependência sumir de novo, o build quebra antes de virar release.

## Rodando do código

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/baixar_ffmpeg.py    # traz ffmpeg + ffprobe
.venv/bin/python main.py
```

## Testes

```bash
# Baixa DE VERDADE de cada site e confere tamanho e duração do arquivo
.venv/bin/python tests/testar_downloads.py

# Prova que as dependências estão dentro do app empacotado
./dist/BaixaFacil.app/Contents/MacOS/BaixaFacil --diagnostico --baixar-teste
```

## Build

```bash
./scripts/build.sh          # só a plataforma atual
```

O PyInstaller **não faz build cruzado**: mac só gera mac, e mac arm64 só gera
arm64. Pras três plataformas, publique uma tag e deixe o
`.github/workflows/build.yml` rodar, ele usa um runner de cada sistema e cria o
Release com os instaladores.

```bash
git tag v2.0.0 && git push origin v2.0.0
```

## Estrutura

| Arquivo | Papel |
|---|---|
| `main.py` | Interface (customtkinter) e o modo `--diagnostico` |
| `baixafacil/motor.py` | Download via `yt_dlp` como biblioteca, progresso e erros em português |
| `baixafacil/binarios.py` | Acha o ffmpeg/ffprobe que vieram no bundle |
| `baixafacil/spotify.py` | Lê metadados do link do Spotify e monta a busca |
| `baixafacil/atualizacao.py` | Checa release novo, baixa e abre o instalador |
| `BaixaFacil.spec` | Receita do PyInstaller, é aqui que o ffmpeg entra no app |
| `scripts/baixar_ffmpeg.py` | Vendoriza os binários estáticos |

## Spotify, Instagram e Facebook

- **Spotify**: o áudio do Spotify é protegido e não dá pra baixar de lá. O app
  lê o nome da música e do artista no link e procura o áudio equivalente. Serve
  pra faixa, álbum e playlist.
- **Instagram** e conteúdo privado do **Facebook**: os sites só entregam a mídia
  pra quem está logado. O app tem a opção *Usar meu login do navegador*, que lê
  os cookies do navegador local. Nada é enviado pra servidor nenhum.

## Uso responsável

Baixe o que você tem direito de baixar: conteúdo próprio, material livre ou com
permissão de quem publicou. Respeite os termos de uso de cada site e os direitos
autorais de cada obra.

---

FlowCore | Leonardo Assis | 2026
