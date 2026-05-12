"""Bangla TTS — Streamlit frontend."""

import io
import os
import urllib.parse

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Bangla TTS",
    page_icon="assets/icon.png" if os.path.exists("assets/icon.png") else None,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .block-container { max-width: 780px; padding-top: 2rem; }
  .stAudio { margin-top: 1rem; }
  .badge { background:#1e3a5f; color:#fff; padding:2px 8px;
           border-radius:4px; font-size:.8rem; }
</style>
""", unsafe_allow_html=True)

# ── header ────────────────────────────────────────────────────────────────────
st.title("Bangla Text-to-Speech")
st.caption("Powered by Gemma (normalisation) + gTTS (synthesis)")
st.divider()

# ── sidebar: settings ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    model   = st.text_input("Gemma model", value="gemma3:4b")
    slow    = st.checkbox("Slow speech", value=False)
    do_norm = st.checkbox("Normalize text with Gemma", value=True,
                          help="Expand numbers, abbreviations before synthesis")
    st.divider()
    if st.button("Check API health"):
        try:
            r = requests.get(f"{API_URL}/health", timeout=5)
            data = r.json()
            st.json(data)
        except Exception as exc:
            st.error(f"Cannot reach API: {exc}")

# ── main area ─────────────────────────────────────────────────────────────────
text = st.text_area(
    "Enter Bangla text",
    placeholder="এখানে বাংলা লিখুন…",
    height=180,
    max_chars=5000,
)

char_count = len(text)
st.caption(f"{char_count} / 5000 characters")

col_gen, col_norm = st.columns([1, 1])

with col_gen:
    generate = st.button("Generate Speech", type="primary", use_container_width=True)

with col_norm:
    normalize_only = st.button("Normalize only", use_container_width=True)

# ── normalize-only action ─────────────────────────────────────────────────────
if normalize_only:
    if not text.strip():
        st.warning("Please enter some Bangla text first.")
    else:
        with st.spinner("Normalizing with Gemma…"):
            try:
                r = requests.post(
                    f"{API_URL}/tts/normalize",
                    json={"text": text, "model": model},
                    timeout=60,
                )
                if r.ok:
                    data = r.json()
                    st.success("Normalization complete")
                    st.markdown("**Original:**")
                    st.code(data["original"], language=None)
                    st.markdown("**Normalized:**")
                    st.code(data["normalized"], language=None)
                else:
                    st.error(r.json().get("detail", "Unknown error"))
            except requests.exceptions.ConnectionError:
                st.error(f"Cannot connect to API at {API_URL}")
            except Exception as exc:
                st.error(str(exc))

# ── generate speech action ────────────────────────────────────────────────────
if generate:
    if not text.strip():
        st.warning("Please enter some Bangla text first.")
    else:
        with st.spinner("Synthesizing speech…"):
            try:
                r = requests.post(
                    f"{API_URL}/tts",
                    json={
                        "text":      text,
                        "model":     model,
                        "normalize": do_norm,
                        "slow":      slow,
                    },
                    timeout=120,
                )

                if r.ok:
                    # show normalized text if available
                    norm_header = r.headers.get("X-Normalized-Text", "")
                    if norm_header and do_norm:
                        normalized = urllib.parse.unquote(norm_header)
                        with st.expander("Normalized text (what was spoken)", expanded=True):
                            st.write(normalized)

                    st.audio(r.content, format="audio/mp3")

                    st.download_button(
                        label="Download MP3",
                        data=r.content,
                        file_name="bangla_tts.mp3",
                        mime="audio/mpeg",
                        use_container_width=True,
                    )
                    st.success(f"Done — {len(r.content) / 1024:.1f} KB audio generated")

                else:
                    detail = r.json().get("detail", r.text)
                    st.error(f"API error {r.status_code}: {detail}")

            except requests.exceptions.ConnectionError:
                st.error(f"Cannot connect to API at {API_URL}. Is the backend running?")
            except requests.exceptions.Timeout:
                st.error("Request timed out — the model may still be loading.")
            except Exception as exc:
                st.error(str(exc))

# ── footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("API: [/api/docs](/api/docs) | [/health](/health) | github.com/rejRoky/bangla-tts-gemma")
