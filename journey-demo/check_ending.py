"""Verify the tail omitted by the model's first full-video sampling pass."""
import argparse
import base64
from pathlib import Path
from analyze import load_config, request_model
from schemas import obj, array, text, number, strings


parser = argparse.ArgumentParser()
parser.add_argument('--run', type=Path, required=True)
parser.add_argument('--env', type=Path, required=True)
args = parser.parse_args()
schema = obj({'source_start_s': number, 'source_end_s': number,
    'closing_scene_summary': text,
    'timeline': array(obj({'start_s': number, 'end_s': number,
        'visual_evidence': text, 'people_visible': {'type': 'boolean'}}), 1, 15),
    'adds_new_journey_stop': {'type': 'boolean'}, 'new_stop_evidence': text,
    'limitations': strings})
video = args.run / 'input/ending-check.mp4'
prompt = '''This is the final 37.4 seconds of a travel film, beginning at 210 seconds in the original source and ending at 247.4 seconds. The full-video analysis reported uncertainty about its ending. Inspect this actual clip and summarize what visibly happens. Return the required JSON. Use original-source timestamps (add 210 to clip-relative times), bounded by 210 and 247.4. State whether this contains evidence for a new scenic stop or is a closing montage/credits. Do not identify people or invent audio; this copy has no audio. If place names are not visible, retain that uncertainty.'''
request_model(load_config(args.env), args.run / 'analysis', 'ending_check', [
    {'type': 'video_url', 'video_url': {'url': 'data:video/mp4;base64,' + base64.b64encode(video.read_bytes()).decode()}},
    {'type': 'text', 'text': prompt}], 16000, schema)
