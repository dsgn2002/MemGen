import hashlib
import json
import math
import subprocess
import warnings
from pathlib import Path

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

Image.MAX_IMAGE_PIXELS = 50_000_000


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def inspect_upload(path, kind, output):
    """Decode actual bytes, not the client MIME or extension; keep originals."""
    try:
        return _inspect_upload(path, kind, output)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        raise ValueError('Photos must contain at most 50 million pixels.') from e
    except subprocess.TimeoutExpired as e:
        raise ValueError('Media decoding timed out. Try exporting the file again.') from e


def _inspect_upload(path, kind, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if kind == 'photo':
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as im:
                if im.format not in {'JPEG', 'PNG', 'WEBP', 'HEIF', 'HEIC'} or getattr(im, 'n_frames', 1) != 1:
                    raise ValueError('Use a still JPEG, PNG, WebP, or HEIC image.')
                im.load()
                format_name = im.format
                normalized = ImageOps.exif_transpose(im).convert('RGB')
                width, height = normalized.size
                normalized.thumbnail((2048, 2048))
                normalized.save(output / 'normalized.jpg', quality=95)
                normalized.thumbnail((640, 640))
                normalized.save(output / 'preview.jpg', quality=85)
        return {'width': width, 'height': height, 'format': format_name,
                'normalized_sha256': sha256(output / 'normalized.jpg'), 'audio_analyzed': False}
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)],
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError('This file could not be decoded as a video.')
    info = json.loads(result.stdout)
    fmt = info.get('format', {})
    if not {'mov', 'mp4'} & set(fmt.get('format_name', '').split(',')):
        raise ValueError('Use an MP4 or MOV video.')
    streams = [s for s in info['streams'] if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic')]
    if not streams:
        raise ValueError('The file contains no video frames.')
    s = streams[0]
    duration = float(fmt.get('duration', s.get('duration', 0)))
    # Exporters can round a ten-minute cut up to the next video frame.
    # Keep the measured duration; tolerate at most 100 ms, never round minutes.
    if not math.isfinite(duration) or not 0 < duration <= 600.1:
        raise ValueError(f'Videos must be longer than 0 and at most 10 minutes (measured {duration:.3f} seconds).')
    if not 0 < s['width'] <= 4096 or not 0 < s['height'] <= 4096:
        raise ValueError('Videos must be 4K or smaller.')
    args = ['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', str(min(.1, duration / 2)), '-i', str(path),
            '-map', f"0:{s['index']}", '-frames:v', '1', '-vf', 'scale=640:-2', str(output / 'preview.jpg')]
    decoded = subprocess.run(args, capture_output=True, timeout=60)
    if decoded.returncode or not (output / 'preview.jpg').exists():
        raise ValueError('Video decoding failed. Export an H.264 MP4 and upload it again.')
    return {'width': s['width'], 'height': s['height'], 'duration_seconds': duration,
            'codec': s.get('codec_name'), 'video_stream_index': s['index'], 'audio_analyzed': False}
