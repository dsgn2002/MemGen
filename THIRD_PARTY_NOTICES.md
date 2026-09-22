# Third-party notices

## Kenney Space Kit

- Creator: Kenney, https://kenney.nl
- Source: https://kenney.nl/assets/space-kit
- License: Creative Commons Zero (CC0).
- Included source modules: rocket_baseA.glb, rocket_fuelB.glb, rocket_topA.glb.
- Original license: souvenir-sample/assets/kenney/License.txt.
- Modified in the sample by assembling modules and adding a plinth and lettering.

## Interactive viewer

The HTML viewer loads Google model-viewer 4.0.0 from unpkg. See https://github.com/google/model-viewer for its Apache-2.0 license and notices. It is referenced, not vendored.

Python dependencies retain their own licenses. Future AI model weights are not covered by this repository's MIT license.

## Travel reconstruction dependencies

- The reconstruction viewer references Three.js 0.169.0 and its OrbitControls
  module from jsDelivr. They retain the [Three.js MIT license](https://github.com/mrdoob/three.js/blob/r169/LICENSE) and are not vendored.
- Geometry estimation uses [Microsoft MoGe](https://github.com/microsoft/MoGe)
  and the `Ruicheng/moge-2-vits-normal` checkpoint on the compute host. Their
  code, dependency and model licenses remain separate; no weights or vendored
  source trees are included in this repository.
- NVIDIA Omniverse Kit is installed separately and remains subject to NVIDIA's
  license terms. Its packages are not distributed here.
- The demonstration source is [The Hong Kong Outdoor Adventure, by The Travel
  Intern](https://www.youtube.com/watch?v=9jtnoejpLcU). Attribution remains in the
  viewers and run manifests. The source video, extracted frames and textured
  outputs are excluded from this repository and are not relicensed under MIT.
