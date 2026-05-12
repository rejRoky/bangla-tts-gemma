# bangla-tts-gemma

Bangla (Bengali) Text-to-Speech powered by **Gemma** (text normalisation via Ollama) and **gTTS** (speech synthesis).

## How it works

```
Bangla text → Gemma (Ollama) normalises → gTTS synthesises → MP3 audio
```

Gemma expands numerals, abbreviations, and cleans mixed-script text before passing to gTTS which supports Bangla (`bn`) natively.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally
- Internet connection (for gTTS synthesis)

## Setup

```bash
# 1. Install dependencies
bash setup.sh

# 2. Activate virtual environment
source .venv/bin/activate
```

## Usage

```bash
# Speak text aloud
python tts.py "আমার সোনার বাংলা"

# Save to MP3
python tts.py "বাংলাদেশ" -o output.mp3

# Use a specific Ollama model
python tts.py --model gemma3:4b "আজকের তারিখ ১২-০৫-২০২৬"

# Skip Gemma normalisation (faster, no Ollama needed)
python tts.py --no-normalize "বাংলাদেশ"

# Slower speech rate
python tts.py --slow "আমার সোনার বাংলা"

# Launch Gradio web UI
python tts.py --ui
```

## Environment variable

```bash
export GEMMA_MODEL=gemma3:4b   # default model name
```

## Example

```
Input  : আজকের তারিখ ১২-০৫-২০২৬ এবং তাপমাত্রা ৩২ ডিগ্রি।
Gemma  : আজকের তারিখ বারো মে দুই হাজার সাতাশ এবং তাপমাত্রা পঁয়ত্রিশ ডিগ্রি।
Output : output.mp3
```

## License

MIT
