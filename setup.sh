#!/usr/bin/env bash
# Setup script for Bangla TTS (Gemma 4 + gTTS)
set -e

echo "=== Step 1: Install pip ==="
sudo apt-get install -y python3-pip

echo "=== Step 2: Create virtual environment ==="
python3 -m venv .venv
source .venv/bin/activate

echo "=== Step 3: Install Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Step 4: Install Ollama (if not present) ==="
export PATH="$PATH:$HOME/.local/bin"
if ! command -v ollama &>/dev/null; then
    LATEST=$(curl -s https://api.github.com/repos/ollama/ollama/releases/latest | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
    mkdir -p "$HOME/.local/bin"
    curl -L "https://github.com/ollama/ollama/releases/download/${LATEST}/ollama-linux-amd64.tar.zst" \
        | tar --use-compress-program=unzstd -xf - bin/ollama
    cp bin/ollama "$HOME/.local/bin/ollama"
    chmod +x "$HOME/.local/bin/ollama"
    echo "Ollama installed to ~/.local/bin/ollama — add to PATH: export PATH=\"\$PATH:\$HOME/.local/bin\""
else
    echo "Ollama already installed: $(ollama --version)"
fi

echo "=== Step 5: Start Ollama server ==="
ollama serve &>/tmp/ollama.log &
sleep 3

echo "=== Step 6: Pull Gemma model ==="
# gemma4 if available, otherwise gemma3:4b
ollama pull gemma4 2>/dev/null || ollama pull gemma3:4b

echo ""
echo "✓ Setup complete!"
echo ""
echo "Usage:"
echo "  source .venv/bin/activate"
echo "  python tts.py \"আমার সোনার বাংলা\""
echo "  python tts.py \"আমার সোনার বাংলা\" -o output.mp3"
echo "  python tts.py --ui          # launch web UI"
