# My Travel Journey introduction video

**Final video:** `my-travel-journey-introduction.mp4`  
**Runtime:** 4 minutes 20 seconds  
**Format:** 1920 × 1080, 24 fps, H.264/AAC  
**Audio:** English ElevenLabs Multilingual v2 narration (Sarah) with an original instrumental bed  
**Subtitles:** Burned-in Simplified Chinese; matching `subtitles.zh-Hans.srt` included

The animated opening shows a traveler imagining an explorable 3D travel map. A
small **Team R∞** mark appears throughout. Existing public Sai Kung and Hong Kong
tram examples are labeled separately from the private dining and lantern result.
Refined animation in the private result is labeled as a curated presentation edit.

The agentic skills sequence uses an actual Sai Kung run to explain [Trip Intent
Understanding](../../skills/trip-intent-understanding/SKILL.md) and [Video Evidence
Selection](../../skills/video-evidence-selection/SKILL.md). It shows Qwen observations,
frame sampling and refinement, source timestamps, uncertainty, and a proposal for
traveler review. **Qwen3.6-27B** inference ran locally on a DGX Spark unit that the
team accessed remotely. Hardware performance specifications are omitted so the
skills receive the emphasis.

`script.txt` and `cues.json` contain the timed English narration and Chinese
subtitles. `poster.jpg` is a preview. `narration.m4a` and `soundtrack.m4a` are
compact audio stems for editing. Raw WAV and temporary render frames remain in
the production workspace.

## Source and technology notes

- Sai Kung sample footage: [The Travel Intern, Hong Kong Outdoor Adventure](https://www.youtube.com/watch?v=9jtnoejpLcU).
- Hong Kong tram footage: [michaelinlondon, *Hong Kong Trams, September 2009*](https://commons.wikimedia.org/wiki/File:Hong_Kong_Trams,_September_2009-UKNqZzl2cu8.webm), [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
- Qwen3.6-27B is documented in [Qwen's model card](https://huggingface.co/Qwen/Qwen3.6-27B). The separate image styling and 3D generation stages use Qwen Image Edit and TRELLIS.2. Omniverse assembly and RTX rendering are shown for the scenic public examples; the private uploaded miniatures do not claim Omniverse export.

All 3D results are source-guided interpretations. Hidden geometry, scene layout,
lighting variants, and curated animations are not exact reconstructions of the
original footage.
