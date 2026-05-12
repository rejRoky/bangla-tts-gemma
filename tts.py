#!/usr/bin/env python3
"""Bangla TTS — Gemma 4 normalizes text, gTTS synthesizes speech."""

import argparse
import os
import shutil
import sys
import tempfile

# ── dependencies ──────────────────────────────────────────────────────────────

try:
    import ollama
except ImportError:
    sys.exit("Error: run  pip install ollama")

try:
    from gtts import gTTS
except ImportError:
    sys.exit("Error: run  pip install gtts")

import subprocess

# find a system MP3 player (mpg123 > ffplay > aplay-via-ffmpeg fallback)
def _find_player() -> list[str] | None:
    for cmd in (["mpg123", "-q"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
                ["mplayer", "-really-quiet"], ["cvlc", "--play-and-exit"]):
        if shutil.which(cmd[0]):
            return cmd
    return None

_PLAYER = _find_player()

# ── config ────────────────────────────────────────────────────────────────────

GEMMA_MODEL = os.environ.get("GEMMA_MODEL", "gemma4")

_SYSTEM = """\
You are a Bangla text preprocessor for a Text-to-Speech engine.
Normalize the input Bangla text so it sounds natural when spoken:
- Expand Bangla numerals and digits to their word form (e.g. ৩ → তিন, 2025 → দুই হাজার পঁচিশ)
- Expand common abbreviations to full Bangla words
- Add natural pauses by ensuring sentences end with a period or comma
- Remove HTML tags, URLs, and non-Bangla/punctuation characters
- Keep the language strictly Bangla

Return ONLY the cleaned Bangla text — no explanations, no English."""

# ── core functions ─────────────────────────────────────────────────────────────

def normalize(text: str, model: str = GEMMA_MODEL) -> str:
    """Use Gemma 4 via Ollama to normalise Bangla text for TTS."""
    try:
        resp = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": text},
            ],
        )
        return resp["message"]["content"].strip()
    except Exception as exc:
        print(f"[warn] Gemma normalisation skipped: {exc}")
        return text


def synthesize(text: str, slow: bool = False) -> str:
    """Convert Bangla text to an MP3 file using gTTS; returns the file path."""
    tts = gTTS(text=text, lang="bn", slow=slow)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tts.save(tmp.name)
    return tmp.name


def play_audio(path: str) -> None:
    """Play an MP3 file — tries system players, then pydub+aplay fallback."""
    if _PLAYER:
        subprocess.run([*_PLAYER, path], check=True)
        return
    # pydub + aplay fallback (converts MP3→WAV in memory, plays via aplay)
    try:
        from pydub import AudioSegment
        import wave, array
        audio = AudioSegment.from_mp3(path)
        wav_path = path.replace(".mp3", ".wav")
        audio.export(wav_path, format="wav")
        subprocess.run(["aplay", "-q", wav_path], check=True)
        os.unlink(wav_path)
    except Exception as exc:
        print(f"Audio saved: {path}  (playback failed: {exc})")


def run(
    text: str,
    output: str | None = None,
    skip_normalize: bool = False,
    slow: bool = False,
    model: str = GEMMA_MODEL,
) -> str:
    """Full pipeline: normalise → synthesise → play or save. Returns audio path."""
    print(f"Input  : {text}")

    if not skip_normalize:
        print(f"Normalising with {model}…")
        text = normalize(text, model=model)
        print(f"Cleaned: {text}")

    print("Synthesising speech…")
    audio = synthesize(text, slow=slow)

    if output:
        shutil.move(audio, output)
        print(f"Saved  : {output}")
        return output

    play_audio(audio)
    os.unlink(audio)
    return ""


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli() -> None:
    p = argparse.ArgumentParser(
        description="Bangla TTS powered by Gemma 4 + gTTS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  python tts.py "আমার সোনার বাংলা"
  python tts.py "আমার সোনার বাংলা" -o output.mp3
  python tts.py --model gemma4 "আজকের তারিখ ১২-০৫-২০২৬"
  GEMMA_MODEL=gemma4 python tts.py "বাংলাদেশ"
""",
    )
    p.add_argument("text",        nargs="?",           help="Bangla text to speak")
    p.add_argument("-o", "--output",                   help="Save audio to MP3 file")
    p.add_argument("--model",     default=GEMMA_MODEL, help=f"Ollama model  [default: {GEMMA_MODEL}]")
    p.add_argument("--no-normalize", action="store_true", help="Skip Gemma normalisation")
    p.add_argument("--slow",      action="store_true", help="Slower speech rate")
    args = p.parse_args()

    text = args.text or input("Enter Bangla text: ").strip()
    if not text:
        p.error("No text provided.")

    run(text, output=args.output, skip_normalize=args.no_normalize,
        slow=args.slow, model=args.model)


# ── Gradio web UI (optional) ──────────────────────────────────────────────────

def launch_ui() -> None:
    try:
        import gradio as gr
    except ImportError:
        sys.exit("Error: run  pip install gradio")

    def process(text, model, slow, skip_norm):
        if not text.strip():
            return None, "Please enter some Bangla text."
        tmp = tempfile.mktemp(suffix=".mp3")
        try:
            run(text, output=tmp, skip_normalize=skip_norm, slow=slow, model=model)
            return tmp, "Done!"
        except Exception as exc:
            return None, f"Error: {exc}"

    with gr.Blocks(title="Bangla TTS — Gemma 4") as demo:
        gr.Markdown("# Bangla TTS\nPowered by **Gemma 4** (text normalisation) + **gTTS** (speech synthesis)")

        with gr.Row():
            with gr.Column():
                text_in  = gr.Textbox(label="Bangla text", lines=4,
                                      placeholder="এখানে বাংলা লিখুন…")
                model_in = gr.Textbox(label="Ollama model", value=GEMMA_MODEL)
                with gr.Row():
                    slow_cb     = gr.Checkbox(label="Slow speech")
                    nonorm_cb   = gr.Checkbox(label="Skip Gemma normalisation")
                btn = gr.Button("Generate Speech", variant="primary")
            with gr.Column():
                audio_out  = gr.Audio(label="Output audio", type="filepath")
                status_out = gr.Textbox(label="Status", interactive=False)

        btn.click(process,
                  inputs=[text_in, model_in, slow_cb, nonorm_cb],
                  outputs=[audio_out, status_out])

    demo.launch()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--ui" in sys.argv:
        sys.argv.remove("--ui")
        launch_ui()
    else:
        _cli()
