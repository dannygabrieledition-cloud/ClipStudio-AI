"""Streamlit frontend: run `streamlit run app.py`."""
from pathlib import Path
import io
import shutil
import tempfile
import zipfile
import streamlit as st
from engine import probe, transcribe, pick_clips, render_clip, save_manifest

st.set_page_config(page_title="ClipStudio AI", page_icon="🎬", layout="wide")
st.title("🎬 ClipStudio AI")
st.caption("De videos largos a clips verticales listos para redes sociales")
st.info("Versión web: sube archivos originales para los que tengas permiso de edición. No descarga videos de YouTube.")
st.warning("Prueba inicial en alojamiento gratuito: utiliza videos cortos, idealmente de 1 a 5 minutos y menos de 100 MB. El procesamiento consume recursos y podría detenerse por límites del servidor.")

# Password gate for shared cloud deployments (optional; configure APP_PASSWORD in Streamlit secrets).
try:
    password = st.secrets.get("APP_PASSWORD", "")
except Exception:
    password = ""
if password:
    attempt = st.text_input("Contraseña de acceso", type="password")
    if attempt != password:
        st.stop()

with st.sidebar:
    st.header("Configuración")
    count = st.slider("Número de clips", 1, 5, 3)
    target = st.slider("Duración objetivo (segundos)", 20, 90, 40, 5)
    model = st.selectbox("Modelo de transcripción", ["tiny", "base"], index=0, help="Para la prueba en la nube recomendamos tiny; base mejora precisión, pero consume más memoria.")
    lang = st.selectbox("Idioma", ["es", "auto", "en", "pt"], index=0)
    layout = st.selectbox("Encuadre vertical", ["Fondo difuminado (no recorta)", "Recorte central (llena pantalla)"])
    captions = st.checkbox("Incrustar subtítulos", value=True)
    resolution = 720
    st.caption("Exportación a 720 × 1280 para la versión web inicial.")

uploaded = st.file_uploader("Sube un video autorizado", type=["mp4", "mov", "mkv", "webm"])
permission = st.checkbox("Confirmo que cuento con autorización para editar este video.")
if uploaded:
    if uploaded.size > 100 * 1024 * 1024:
        st.error("Para esta prueba web, usa un archivo de 100 MB o menos.")
        st.stop()
    st.video(uploaded)
    st.caption(f"Archivo: {uploaded.name} · {uploaded.size / (1024*1024):.1f} MB")

if "processed" not in st.session_state: st.session_state.processed = None

if st.button("✨ Generar clips", type="primary", disabled=not(uploaded and permission)):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        st.error("FFmpeg y ffprobe no están instalados o no están en PATH. Consulta el README.")
    else:
        with st.status("Procesando video…", expanded=True) as status:
            work = Path(tempfile.mkdtemp(prefix="clipstudio_"))
            suffix = Path(uploaded.name).suffix.lower()
            source = work / ("video" + suffix)
            with source.open("wb") as f:
                uploaded.seek(0)
                shutil.copyfileobj(uploaded, f)
            try:
                info = probe(source)
                if not info["audio"]: raise ValueError("El video no tiene audio; esta versión necesita voz para identificar clips.")
                st.write(f"Duración: {info['duration'] / 60:.1f} minutos. Transcribiendo…")
                speeches = transcribe(source, model, lang)
                if not speeches: raise ValueError("No se detectó voz. Prueba con un video con diálogo claro.")
                clips = pick_clips(speeches, info["duration"], target, count)
                if not clips: raise ValueError("No hay suficientes segmentos hablados para crear clips de esa duración. Reduce la duración objetivo.")
                st.write(f"Generando {len(clips)} clips en 9:16…")
                outputs = []
                bar = st.progress(0)
                for i, clip in enumerate(clips, 1):
                    output = work / f"clip_{i:02}.mp4"
                    render_clip(source, clip, speeches, output, captions, "crop" if layout.startswith("Recorte") else "blur", resolution)
                    outputs.append(output)
                    bar.progress(i / len(clips))
                save_manifest(work / "resultados.json", clips, speeches)
                archive = io.BytesIO()
                with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in outputs + [work / "resultados.json"]: z.write(f, f.name)
                st.session_state.processed = {
                    "clips": clips, "outputs": [f.read_bytes() for f in outputs], "zip": archive.getvalue(), "transcript": speeches
                }
                status.update(label="¡Clips generados!", state="complete")
            except Exception as exc:
                status.update(label="No se pudo completar", state="error")
                st.error(f"Error: {exc}")
            finally:
                shutil.rmtree(work, ignore_errors=True)

if st.session_state.processed:
    result = st.session_state.processed
    st.subheader("Tus clips")
    st.download_button("⬇️ Descargar todos los clips (ZIP)", result["zip"], file_name="clipstudio_resultados.zip", mime="application/zip", type="primary")
    st.caption("La puntuación estima el atractivo del guion mediante reglas lingüísticas; no predice visualizaciones ni viralidad.")
    for i, (clip, content) in enumerate(zip(result["clips"], result["outputs"]), 1):
        with st.container(border=True):
            a, b = st.columns([1, 2])
            with a: st.video(content)
            with b:
                st.markdown(f"### #{i} · {clip.title}")
                st.metric("Puntuación editorial", f"{clip.score}/99")
                st.write(f"⏱️ {clip.start:.1f}–{clip.end:.1f} segundos · {clip.reason}")
                st.write(clip.text[:700] + ("…" if len(clip.text)>700 else ""))
                st.download_button("Descargar MP4", content, file_name=f"clip_{i:02}.mp4", mime="video/mp4", key=f"download_{i}")
    with st.expander("Transcripción completa"):
        st.write(" ".join(s.text for s in result["transcript"]))
