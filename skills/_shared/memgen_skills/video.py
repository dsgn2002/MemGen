"""Deterministic source discovery and bounded frame extraction using FFmpeg."""
import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from .common import command, finite_positive, sha256


def probe(video):
    video = Path(video).expanduser().resolve()
    if not video.is_file():
        raise ValueError(f"Video does not exist: {video}")
    data = json.loads(command(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", video]))
    stream = next((s for s in data.get("streams", []) if s["codec_type"] == "video"), None)
    if not stream:
        raise ValueError("Input has no video stream")
    duration = finite_positive(data.get("format", {}).get("duration", stream.get("duration", 0)), "Video duration")
    return {"filename": video.name, "sha256": sha256(video), "duration_seconds": duration,
            "width": int(stream["width"]), "height": int(stream["height"]),
            "audio_analyzed": False, "video_stream_index": stream["index"]}


def uniform_times(duration, budget):
    if budget < 1:
        return []
    # Avoid the first/last decoding boundary and repeated times on very short clips.
    count = min(budget, max(1, math.ceil(duration * 2)))
    return sorted(set(round(duration * (i + .5) / count, 4) for i in range(count)))


def discover_shots(video, duration):
    # showinfo writes stderr, unlike ffprobe JSON. Keep failures explicit.
    import subprocess
    result = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(video), "-an",
                             "-vf", "scale=160:-2,fps=2,select='gt(scene,0.28)',showinfo",
                             "-fps_mode", "vfr", "-f", "null", "-"],
                            capture_output=True, text=True, timeout=max(180, int(duration * 3)))
    if result.returncode:
        raise RuntimeError("Shot detection failed: " + result.stderr[-1500:])
    cuts = {float(v) for v in re.findall(r"pts_time:([\d.]+)", result.stderr)}
    return [0.] + sorted(t for t in cuts if .15 < t < duration - .15) + [duration]


def candidate_times(duration, budget, shots, strategy):
    if strategy == "uniform":
        return uniform_times(duration, budget)
    grid = uniform_times(duration, max(1, math.ceil(budget * 2 / 3)))
    centers = [(a + b) / 2 for a, b in zip(shots, shots[1:])]
    remaining = budget - len(grid)
    chosen = []
    # Farthest from current coverage first, with deterministic temporal tie breaks.
    for _ in range(remaining):
        available = [t for t in centers if all(abs(t - x) >= .2 for x in grid + chosen)]
        if not available:
            break
        chosen.append(max(available, key=lambda t: (min(abs(t - x) for x in grid + chosen), -t)))
    if len(grid + chosen) < budget:
        for t in uniform_times(duration, budget):
            if all(abs(t - x) >= .2 for x in grid + chosen):
                chosen.append(t)
                if len(grid + chosen) == budget:
                    break
    return sorted(round(t, 4) for t in grid + chosen)


def shot_interval(timestamp, shots):
    for start, end in zip(shots, shots[1:]):
        if start <= timestamp < end:
            return [start, end]
    raise ValueError("Frame timestamp lies outside shot intervals")


def image_metrics(path):
    with Image.open(path) as original:
        grey = np.asarray(ImageOps.grayscale(original).resize((160, 90)), dtype=float)
        tiny = np.asarray(ImageOps.grayscale(original).resize((9, 8)), dtype=float)
    laplacian = -4 * grey[1:-1, 1:-1] + grey[2:, 1:-1] + grey[:-2, 1:-1] + grey[1:-1, 2:] + grey[1:-1, :-2]
    bits = (tiny[:, 1:] > tiny[:, :-1]).flatten()
    fingerprint = sum(int(bit) << i for i, bit in enumerate(bits))
    return {"sharpness": round(float(laplacian.var()), 4), "brightness": round(float(grey.mean() / 255), 4),
            "dark_fraction": round(float((grey < 12).mean()), 4),
            "bright_fraction": round(float((grey > 243).mean()), 4), "dhash": f"{fingerprint:016x}"}


def distance(a, b):
    return (int(a, 16) ^ int(b, 16)).bit_count()


def extract_frames(video, timestamps, run, shots, start_index=0):
    frames = []
    assets = run / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for index, timestamp in enumerate(timestamps, start_index):
        identifier = f"frame-{index:04d}"
        relative = f"assets/{identifier}.jpg"
        path = run / relative
        command(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{timestamp:.4f}", "-i", video,
                 "-map", "0:v:0", "-frames:v", "1", "-vf", "scale='min(960,iw)':-2", "-q:v", "2", path])
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f"Failed to extract requested source frame at {timestamp:.4f}s")
        frames.append({"id": identifier, "timestamp_s": timestamp, "image": relative,
                       "sha256": sha256(path), "shot_range_s": shot_interval(timestamp, shots),
                       "quality": image_metrics(path)})
    return frames


def make_contact_sheet(frames, run, output, labels=None):
    columns = min(3, max(1, len(frames)))
    rows = max(1, math.ceil(len(frames) / columns))
    sheet = Image.new("RGB", (columns * 320, rows * 220), "#11232b")
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        x, y = (index % columns) * 320, (index // columns) * 220
        with Image.open(run / frame["image"]) as im:
            thumb = ImageOps.contain(im.convert("RGB"), (312, 174))
            sheet.paste(thumb, (x + 4, y + 4))
        label = labels[index] if labels else frame["id"]
        draw.text((x + 8, y + 182), f"{label} | {frame['timestamp_s']:.2f}s", fill="white")
    if not frames:
        draw.text((10, 20), "No supported moments selected; read review.md", fill="white")
    sheet.save(output, quality=90)


def clip(video, start, end, path):
    command(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{start:.4f}", "-i", video,
             "-t", f"{end - start:.4f}", "-map", "0:v:0", "-an", "-vf", "scale='min(960,iw)':-2",
             "-c:v", "libx264", "-crf", "25", "-preset", "fast", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", path])
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError("Preview clip was not produced")
