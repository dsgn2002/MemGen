"""Local Qwen video understanding and image styling for the Sai Kung sample."""
import argparse
import json
import os
import time
from pathlib import Path

os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
ROOT = Path("/home/Developer/travel_journey_map")
RUN = ROOT / "runs/2026-09-26-sai-kung-map"


def save(name, value):
    p = RUN / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2) + "\n")


def extract():
    import cv2
    from PIL import Image, ImageDraw
    frames = []
    capture = cv2.VideoCapture(str(ROOT / "runs/2026-09-22-demo/input/source.mp4"))
    for timestamp in [40, 50, 55, 60, 70, 80, 90, 98, 105]:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"Cannot read source frame {timestamp}")
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        image.thumbnail((960, 960))
        image.save(RUN / f"input/frame-{timestamp}.jpg", quality=92)
        frames.append(image)
    capture.release()
    sheet = Image.new("RGB", (960, 630), "#102128")
    draw = ImageDraw.Draw(sheet)
    for index, (stamp, image) in enumerate(zip([40, 50, 55, 60, 70, 80, 90, 98, 105], frames)):
        image = image.copy()
        image.thumbnail((320, 180))
        x, y = index % 3 * 320, index // 3 * 210
        sheet.paste(image, (x, y))
        draw.text((x + 8, y + 184), f"Source {stamp}s", fill="white")
    sheet.save(RUN / "input/contact-sheet.jpg", quality=88)


def understand():
    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText
    start = time.monotonic()
    checkpoint = ROOT / "models/qwen3.6-27b"
    processor = AutoProcessor.from_pretrained(checkpoint, local_files_only=True)
    content = []
    for stamp in [40, 50, 55, 60, 70, 80, 90, 98, 105]:
        content += [{"type": "text", "text": f"Video timestamp {stamp} seconds:"},
                    {"type": "image", "url": str(RUN / f"input/frame-{stamp}.jpg")}]
    prompt = (
        "These chronological frames show the Sai Kung chapter and the transition to Lantau in a Hong Kong travel video. Exclude Lantau from the proposed Sai Kung map. "
        "Design an interactive stylized 3D nature travel map grounded in the visible evidence. "
        "Do not invent exact geographic coordinates or identify people by name. "
        "Return only JSON with keys title, summary, observed_locations (list of objects with name, "
        "source_seconds, visual_evidence, confidence), traveler_appearance, palette, "
        "map_design, suggested_interactions, uncertainties. Include the boat ride and coastal hike "
        "if supported. Be concise, around 450 words maximum. Distinguish observations from design suggestions."
    )
    content.append({"type": "text", "text": prompt})
    messages = [{"role": "user", "content": content}]
    inputs = processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
        return_dict=True, return_tensors="pt", enable_thinking=False,
        images_kwargs={"size": {"longest_edge": 262144, "shortest_edge": 4096}})
    print("Loading Qwen VLM", flush=True)
    model = AutoModelForImageTextToText.from_pretrained(checkpoint, dtype=torch.bfloat16,
        device_map="cuda", attn_implementation="sdpa", local_files_only=True)
    inputs = inputs.to("cuda")
    print("VLM inference", {k: list(v.shape) for k, v in inputs.items() if hasattr(v, "shape")}, flush=True)
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=1100, do_sample=False)
    text = processor.batch_decode(output[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
    (RUN / "analysis/qwen-summary.txt").write_text(text)
    save("analysis/vlm-provenance.json", {"model": str(checkpoint), "timestamps": [40, 50, 55, 60, 70, 80, 90, 98, 105],
        "method": "chronological sampled video frames", "prompt": prompt, "seconds": time.monotonic() - start})
    try:
        save("analysis/journey.json", json.loads(text[text.index("{"):text.rindex("}") + 1]))
    except (ValueError, json.JSONDecodeError):
        save("analysis/journey.json", {"title": "Sai Kung · Sea to Summit", "summary": text})
    print("VLM_COMPLETE", flush=True)


def style():
    import torch
    from PIL import Image
    from diffusers import QwenImageEditPlusPipeline
    checkpoint = ROOT / "models/qwen-image-edit-2511"
    print("Loading image editing model", flush=True)
    pipe = QwenImageEditPlusPipeline.from_pretrained(checkpoint, torch_dtype=torch.bfloat16, local_files_only=True)
    pipe.to("cuda")
    pipe.vae.enable_tiling()
    designs = {
        "coast": (98, "Transform the landscape in this photo into an exquisite complete miniature 3D game environment asset. A compact elevated island with lush rounded green hills, a winding pale coastal hiking path, sandy crescent beach, layered weathered rock cliffs and a little sheltered turquoise bay. Preserve the visible landscape character. Isometric three-quarter view showing the entire island and its solid base, centered with generous margin on a pure white background. Polished animated feature film style, detailed natural textures, warm soft lighting, rich green and turquoise colors. Remove all people, text, logos and overlays. One coherent isolated landmass, no rectangular photograph border."),
        "traveler": (98, "Create one full-body stylized 3D animated movie character based on the foreground hiker in this photo. Retain the visible pale pink T-shirt, dark shorts, black crossbody bag, hair and skin tone. Friendly adult traveler, attractive sculpted face, realistic fabric textures, hiking shoes. Show the entire single character front three-quarter view in a relaxed A-pose with arms separated from torso, both legs and feet fully visible. Center on pure white background, generous margin around body, soft even studio lighting. Remove scenery, other people, text and logos."),
        "boat": (60, "Create a beautiful isolated miniature 3D game asset of the tour boat seen in this photo. Small white passenger boat with a green canopy roof, open sides, benches and wooden deck, complete hull clearly visible from elevated three-quarter side view. Polished stylized animated film quality, realistic painted wood and fabric textures, soft studio lighting, pure white background. No people, no water, no scenery, no text, no logos. Entire boat centered with generous margin, one coherent object.")
    }
    for index, (name, (stamp, prompt)) in enumerate(designs.items()):
        path = RUN / f"output/{name}-style.png"
        if path.exists():
            print("Already styled", name, flush=True)
            continue
        source = Image.open(RUN / f"input/frame-{stamp}.jpg").convert("RGB")
        if name == "traveler":
            # Source frame is 960x540; isolate the visible hiker before styling.
            source = source.crop((145, 275, 295, 540))
        source.thumbnail((640, 640))
        print("STYLING", name, flush=True)
        start = time.monotonic()
        with torch.inference_mode():
            image = pipe(image=[source], prompt=prompt, negative_prompt=" ",
                width=640, height=640, num_inference_steps=24, true_cfg_scale=4.0,
                generator=torch.Generator(device="cuda").manual_seed(170 + index)).images[0]
        image.save(path)
        save(f"analysis/{name}-style.json", {"model": str(checkpoint), "source_seconds": stamp,
            "prompt": prompt, "steps": 24, "seed": 170 + index, "seconds": time.monotonic() - start})
        print("STYLE_COMPLETE", name, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["extract", "understand", "style"])
    args = parser.parse_args()
    for folder in ["input", "analysis", "output", "logs"]:
        (RUN / folder).mkdir(parents=True, exist_ok=True)
    globals()[args.stage]()
