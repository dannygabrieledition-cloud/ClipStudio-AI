"""ClipStudio AI: local, permission-based video processing engine."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import re
import subprocess
import textwrap
import unicodedata

HOOKS = ("como", "por qué", "porque", "nunca", "siempre", "error", "secreto", "importante", "atención", "descubre", "sabías", "clave", "consejo", "evita", "mejor", "problema", "solución", "tres", "cinco", "primero", "nadie", "realmente")

@dataclass
class Speech:
    start: float
    end: float
    text: str

@dataclass
class Clip:
    start: float
    end: float
    score: int
    title: str
    reason: str
    text: str

def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout)[-1800:])
    return p.stdout

def probe(path: Path) -> dict:
    result = run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", str(path)])
    data = json.loads(result)
    streams = data.get("streams", [])
    if not any(s.get("codec_type") == "video" for s in streams):
        raise ValueError("El archivo no contiene un flujo de video.")
    duration = float(data.get("format", {}).get("duration", 0))
    if duration <= 0: raise ValueError("No se pudo detectar la duración del video.")
    return {"duration": duration, "video": next(s for s in streams if s.get("codec_type") == "video"), "audio": any(s.get("codec_type") == "audio" for s in streams)}

def transcribe(path: Path, model_size="base", language="es") -> list[Speech]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Instala las dependencias: pip install -r requirements.txt") from exc
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(path), language=None if language == "auto" else language, vad_filter=True, beam_size=3)
    return [Speech(float(s.start), float(s.end), s.text.strip()) for s in segments if s.text.strip()]

def normalize(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode("ascii")

def score_text(text: str, duration: float) -> tuple[int, str]:
    n = normalize(text)
    hits = sum(1 for h in HOOKS if normalize(h) in n)
    questions = text.count("?") + text.count("¿")
    exclamations = text.count("!") + text.count("¡")
    words = len(text.split())
    density = words / max(duration, 1)
    base = 45 + min(hits, 5) * 7 + min(questions, 3) * 5 + min(exclamations, 2) * 3
    if 1.6 <= density <= 3.7: base += 9
    elif density < 0.8: base -= 15
    if words >= 45: base += 6
    if duration < 20: base -= 7
    score = int(max(1, min(99, base)))
    reason = "Contiene preguntas y un gancho claro" if questions else ("Incluye frases de interés y consejos" if hits else "Fragmento con discurso continuo")
    return score, reason

def make_title(text: str) -> str:
    first = re.split(r"(?<=[.!?])\s+", text.strip())[0].strip(" ¿¡.,:;-\n")
    words = first.split()
    if len(words) > 11: first = " ".join(words[:11]) + "…"
    return (first[:85] or "Momento destacado").strip()

def pick_clips(speeches: list[Speech], duration: float, target: int = 40, count: int = 5) -> list[Clip]:
    """Select transcript-based highlights with sentence-aware cut points when possible."""
    if not speeches: return []
    target = max(15, min(int(target), 120))
    count = max(1, min(int(count), 20))
    candidates: list[Clip] = []
    for i, s in enumerate(speeches):
        start = max(0, s.start)
        best_j = None
        best_delta = float("inf")
        for j in range(i, len(speeches)):
            end = min(duration, speeches[j].end)
            length = end - start
            if length > target * 1.30: break
            if length >= target * 0.65:
                boundary_bonus = -4 if re.search(r"[.!?]\s*$", speeches[j].text) else 0
                delta = abs(target - length) + boundary_bonus
                if delta < best_delta:
                    best_delta, best_j = delta, j
        if best_j is None: continue
        group = speeches[i:best_j+1]
        end = min(duration, group[-1].end)
        transcript = " ".join(x.text for x in group)
        score, why = score_text(transcript, end-start)
        if re.search(r"[.!?]\s*$", group[-1].text): score = min(99, score + 3)
        candidates.append(Clip(start, end, score, make_title(transcript), why, transcript))
    candidates.sort(key=lambda c: (-c.score, abs((c.end-c.start)-target)))
    chosen: list[Clip] = []
    for c in candidates:
        if all(max(0, min(c.end, p.end) - max(c.start, p.start)) < min(c.end-c.start, p.end-p.start) * 0.20 for p in chosen):
            chosen.append(c)
            if len(chosen) >= count: break
    return chosen

def ass_timestamp(t: float) -> str:
    t = max(0, t)
    h, rem = divmod(t, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h)}:{int(m):02}:{sec:05.2f}"

def safe_ass(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")

def make_ass(speeches: list[Speech], clip: Clip, destination: Path) -> None:
    hdr = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,65,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,75,75,250,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [hdr]
    for s in speeches:
        if s.end <= clip.start or s.start >= clip.end: continue
        start, end = max(0,s.start-clip.start), min(clip.end, s.end)-clip.start
        if end - start < 0.08: continue
        # Split long Whisper segments into short, time-proportional caption blocks.
        words = s.text.split()
        groups = [words[k:k+7] for k in range(0, len(words), 7)]
        for k, group in enumerate(groups):
            a = start + (end-start)*k/len(groups)
            b = start + (end-start)*(k+1)/len(groups)
            lines.append(f"Dialogue: 0,{ass_timestamp(a)},{ass_timestamp(b)},Default,,0,0,0,,{safe_ass(' '.join(group))}\n")
    destination.write_text("".join(lines), encoding="utf-8-sig")

def render_clip(source: Path, clip: Clip, speeches: list[Speech], output: Path, subtitle: bool = True, layout="blur", resolution=720) -> None:
    """Render 9:16 MP4. layout='blur' avoids cutting off speakers; 'crop' fills frame."""
    output.parent.mkdir(parents=True, exist_ok=True)
    w, h = int(resolution), int(resolution * 16 / 9)
    if layout == "crop":
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
        filter_complex = f"[0:v]{vf}[out]"
    else:
        # A blurred background keeps the entire original frame visible.
        filter_complex = (f"[0:v]split=2[bg][fg];"
          f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:2[blur];"
          f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[front];"
          f"[blur][front]overlay=(W-w)/2:(H-h)/2,setsar=1[out]")
    assfile = output.with_suffix(".ass")
    if subtitle:
        make_ass(speeches, clip, assfile)
        # Use filtergraph input with escaped path; paths generated are controlled locally.
        escaped = str(assfile.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'").replace("[", "\\[").replace("]", "\\]")
        filter_complex += f";[out]ass='{escaped}'[final]"
        mapped = "[final]"
    else:
        mapped = "[out]"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(clip.start), "-t", str(clip.end-clip.start), "-i", str(source), "-filter_complex", filter_complex, "-map", mapped, "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output)]
    try: run(cmd)
    finally:
        if assfile.exists(): assfile.unlink()

def save_manifest(path: Path, clips: list[Clip], speeches: list[Speech]) -> None:
    path.write_text(json.dumps({"clips": [asdict(c) for c in clips], "transcript": [asdict(s) for s in speeches]}, ensure_ascii=False, indent=2), encoding="utf-8")
