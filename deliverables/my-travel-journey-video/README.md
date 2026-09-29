# My Travel Journey introduction video

**Final video:** `my-travel-journey-introduction.mp4`  
**Runtime:** 3 minutes 30 seconds  
**Format:** 1920 × 1080, 24 fps, H.264/AAC  
**Audio:** English ElevenLabs Multilingual v2 narration with an original, softly mixed instrumental bed  
**Subtitles:** Burned-in Simplified Chinese; matching `subtitles.zh-Hans.srt` is included

The opening starts with **Team R∞** and **My Travel Journey** beside a photoreal
AI avatar based on the supplied reference image. The avatar has simple speech
and body motion, with her opening wish shown in a speech bubble. Mountain and
city memories then appear in a thought cloud, and the
scene dissolves into the product map. Team R∞ remains in the upper-right corner
throughout. The video then records
the existing world map, Sai Kung coast, and Hong Kong tram viewer. The private
upload sequence uses existing workspace screenshots and the actual reviewed
dining/lantern moments. The scenic public examples are separately labeled from
the private upload result. The refined animations are identified as curated
presentation additions. The skills section uses original frames and output from
the Sai Kung Qwen3.6-27B skill run. Its proposal remains unconfirmed because the
requested companions' identities cannot be verified from the source frames.
Three original Sai Kung video frames appear alongside the moving boat and
changing perspectives, with the relevant source frame highlighted.
The coast recording starts paused, shows the **Play motion** click, and then
shows the boat moving. The browser capture verified a 1.68-unit change in its
scene position after playback began. A short animated transition follows the
public viewer's **Create your own** control into the private workspace.
The sunset and night examples use a separate browser capture that follows the
boat; motion is paused for the final night view so the boat remains visible.
The shorter edit keeps narration gaps below three seconds between cues. Its
closing invites viewers to start their own 3D travel journey.

The prior local cut is renamed `my-travel-journey-introduction-previous-2026-09-29.mp4`.
Only the current MP4 is included in the GitHub pull request.

`script.txt` and `cues.json` contain the timed narration and subtitle text.
`poster.jpg` is a video preview. `narration.m4a` and `soundtrack.m4a` are the
English voice and final audio mix. Production scripts, raw audio, and browser
captures remain in the local editing workspace; they are omitted from this
small delivery bundle. No ElevenLabs API key is stored with these files.

## Source and technology notes

- Sai Kung sample footage: [The Travel Intern, Hong Kong Outdoor Adventure](https://www.youtube.com/watch?v=9jtnoejpLcU).
- Hong Kong tram footage: [michaelinlondon, *Hong Kong Trams, September 2009*](https://commons.wikimedia.org/wiki/File:Hong_Kong_Trams,_September_2009-UKNqZzl2cu8.webm), [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
- Qwen3.6-27B runs locally on a DGX Spark unit accessed remotely. The video omits hardware performance specifications to focus on the two implemented agentic skills.
- The [Trip Intent Understanding](../../skills/trip-intent-understanding/SKILL.md) and [Video Evidence Selection](../../skills/video-evidence-selection/SKILL.md) skills produce reviewable evidence proposals, not confirmed choices or 3D meshes.
- Qwen, Qwen Image Edit, and TRELLIS.2 are upstream models. In the scenic sample, Omniverse assembles generated meshes in USD, positions and animates the boat, sets lighting, and renders an RTX preview. The private uploaded miniatures do not claim Omniverse export.

The video treats all 3D results as source-guided interpretations. Hidden geometry,
scene layout, lighting variants, and curated character animations are not exact
reconstructions of the original footage.
