# My Travel Journey introduction video

- **Final video:** `my-travel-journey-introduction.mp4`
- **Runtime:** 3 minutes 30 seconds
- **Format:** 1920 × 1080, 24 fps, H.264/AAC
- **Audio:** English ElevenLabs Multilingual v2 narration (Sarah) with an original instrumental bed
- **Subtitles:** Burned-in Simplified Chinese; matching `subtitles.zh-Hans.srt` included

The opening shows a speaking traveler imagining mountain and city memories in a
thought cloud before the product map appears. **Team R∞** remains in one upper
corner. The tighter edit keeps narration gaps under three seconds between cues.
The ending invites viewers to create their own 3D travel journey.

The video shows the existing public Sai Kung and Hong Kong tram examples, then a
separately labeled private dining and lantern result. The refined animations in
the private result are labeled as curated presentation additions. Its agentic
skills sequence uses an actual Sai Kung run to explain [Trip Intent
Understanding](../../skills/trip-intent-understanding/SKILL.md) and [Video Evidence
Selection](../../skills/video-evidence-selection/SKILL.md). Source timestamps,
selection reasons, and unresolved details are presented as proposals for traveler
review.

**Qwen3.6-27B** ran locally on a DGX Spark unit the team accessed remotely. For
the scenic demonstration, Omniverse assembled generated meshes in USD, positioned
and animated the boat, set lighting, and rendered an RTX preview. The video
shows an actual Sai Kung RTX preview from that stage. The private uploaded
miniatures use a separate image and 3D pipeline and do not claim Omniverse export.

`script.txt` and `cues.json` contain the timed English narration and Chinese
subtitles. `poster.jpg` is a preview. `narration.m4a` and `soundtrack.m4a` are
compact audio stems for editing. Raw WAV and temporary render frames remain in
the production workspace.

## Source and technology notes

- Sai Kung sample footage: [The Travel Intern, Hong Kong Outdoor Adventure](https://www.youtube.com/watch?v=9jtnoejpLcU).
- Hong Kong tram footage: [michaelinlondon, *Hong Kong Trams, September 2009*](https://commons.wikimedia.org/wiki/File:Hong_Kong_Trams,_September_2009-UKNqZzl2cu8.webm), [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
- Model reference: [Qwen3.6-27B model card](https://huggingface.co/Qwen/Qwen3.6-27B). Qwen, Qwen Image Edit, and TRELLIS.2 are upstream models.

All 3D results are source-guided interpretations. Hidden geometry, scene layout,
lighting variants, and curated animations are not exact reconstructions of the
original footage.
