"""Bangla TTS — Streamlit frontend with SSE streaming."""

import base64
import json
import os
import urllib.parse

import requests
import streamlit as st
import streamlit.components.v1 as components

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Bangla TTS",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .block-container { max-width: 780px; padding-top: 2rem; }
  .stAudio { margin-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# ── header ────────────────────────────────────────────────────────────────────
st.title("Bangla Text-to-Speech")
st.caption("Gemma normalisation  •  Microsoft edge-tts synthesis  •  SSE streaming")
st.divider()

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")

    # fetch voices from API
    try:
        vresp = requests.get(f"{API_URL}/tts/voices", timeout=3)
        voice_map: dict = vresp.json()["voices"] if vresp.ok else {}
        default_voice = vresp.json().get("default", "bn-BD-NabanitaNeural") if vresp.ok else "bn-BD-NabanitaNeural"
    except Exception:
        voice_map = {
            "female-bd": "bn-BD-NabanitaNeural",
            "male-bd":   "bn-BD-PradeepNeural",
            "female-in": "bn-IN-TanishaaNeural",
            "male-in":   "bn-IN-BashkarNeural",
        }
        default_voice = "bn-BD-NabanitaNeural"

    voice_label = st.selectbox("Voice", list(voice_map.keys()), index=0)
    voice = voice_map[voice_label]

    model   = st.text_input("Gemma model", value="gemma3:4b")
    slow    = st.checkbox("Slow speech")
    do_norm = st.checkbox("Normalize with Gemma", value=True,
                          help="Expand numbers, abbreviations before synthesis")

    st.divider()
    if st.button("API health"):
        try:
            r = requests.get(f"{API_URL}/health", timeout=5)
            st.json(r.json())
        except Exception as exc:
            st.error(str(exc))

# ── main ──────────────────────────────────────────────────────────────────────
text = st.text_area(
    "Enter Bangla text",
    placeholder="এখানে বাংলা লিখুন…",
    height=180,
    max_chars=5000,
)
st.caption(f"{len(text)} / 5000 characters")

col_gen, col_norm = st.columns([1, 1])
generate       = col_gen.button("Generate Speech", type="primary", use_container_width=True)
normalize_only = col_norm.button("Normalize only",               use_container_width=True)


# ── SSE stream helper ─────────────────────────────────────────────────────────

def stream_tts(payload: dict):
    """POST to /tts/stream and yield parsed SSE events."""
    with requests.post(
        f"{API_URL}/tts/stream",
        json=payload,
        stream=True,
        timeout=180,
    ) as resp:
        resp.raise_for_status()
        for raw in resp.iter_lines(decode_unicode=True):
            if raw.startswith("data: "):
                try:
                    yield json.loads(raw[6:])
                except json.JSONDecodeError:
                    pass


# ── generate speech ───────────────────────────────────────────────────────────

if generate:
    if not text.strip():
        st.warning("Please enter some Bangla text first.")
    else:
        payload = {
            "text":      text,
            "model":     model,
            "normalize": do_norm,
            "slow":      slow,
            "voice":     voice,
        }

        audio_id    = None
        norm_chunks: list[str] = []
        error_msg   = None

        with st.status("Generating Bangla speech…", expanded=True) as status:
            progress_bar = st.progress(0)
            chunk_label  = st.empty()

            try:
                for event in stream_tts(payload):
                    etype = event.get("type")

                    if etype == "start":
                        total = event.get("total_chunks", 1)
                        norm_flag = event.get("normalizing", False)
                        chunk_label.write(
                            f"**{total}** chunk(s) — "
                            + ("normalizing with Gemma…" if norm_flag else "synthesis only (no normalization needed)")
                        )

                    elif etype == "progress":
                        chunk_label.write(event["msg"])

                    elif etype == "chunk_norm":
                        c, t = event["chunk"], event["total"]
                        chunk_label.write(f"Normalized {c}/{t}: _{event.get('preview','')}_")

                    elif etype == "chunk_done":
                        pct = event.get("percent", 100)
                        c, t = event["chunk"], event["total"]
                        progress_bar.progress(pct, text=f"Synthesized {c}/{t} chunk(s)…")

                    elif etype == "ready":
                        audio_id    = event["audio_id"]
                        norm_chunks = event.get("normalized_chunks", [])
                        progress_bar.progress(100, text="Done!")
                        status.update(label="Speech ready!", state="complete", expanded=False)

                    elif etype == "error":
                        error_msg = event["msg"]
                        status.update(label="Failed", state="error")
                        st.error(error_msg)

            except requests.exceptions.ConnectionError:
                status.update(label="Connection error", state="error")
                st.error(f"Cannot reach API at {API_URL}")
            except requests.exceptions.Timeout:
                status.update(label="Timed out", state="error")
                st.error("Request timed out — model may still be loading.")
            except Exception as exc:
                status.update(label="Error", state="error")
                st.error(str(exc))

        if audio_id:
            audio_resp = requests.get(f"{API_URL}/tts/audio/{audio_id}", timeout=30)
            if audio_resp.ok:
                if do_norm and norm_chunks:
                    with st.expander(f"Normalized text ({len(norm_chunks)} chunk(s))"):
                        for i, c in enumerate(norm_chunks, 1):
                            st.markdown(f"**{i}.** {c}")
                audio_b64 = base64.b64encode(audio_resp.content).decode()
                components.html(
                    f"""
                    <audio controls autoplay style="width:100%;margin-top:0.5rem">
                      <source src="data:audio/mpeg;base64,{audio_b64}" type="audio/mpeg">
                    </audio>
                    """,
                    height=60,
                )
                st.download_button(
                    "Download MP3",
                    data=audio_resp.content,
                    file_name="bangla_tts.mp3",
                    mime="audio/mpeg",
                    use_container_width=True,
                )
            else:
                st.error("Audio expired — please generate again.")


# ── normalize only ────────────────────────────────────────────────────────────

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
                    st.success("Done")
                    st.markdown("**Original:**")
                    st.code(data["original"], language=None)
                    st.markdown("**Normalized:**")
                    st.code(data["normalized"], language=None)
                else:
                    st.error(r.json().get("detail", "Unknown error"))
            except Exception as exc:
                st.error(str(exc))


# ── footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("API docs: [/api/docs](/api/docs)  •  Health: [/health](/health)")
