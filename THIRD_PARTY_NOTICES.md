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

Python dependencies retain their own licenses. AI model weights are not covered by this repository's MIT license.

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

## Generated Sai Kung nature map

- Local inference uses Qwen3.6-27B, Qwen-Image-Edit-2511, and
  [Microsoft TRELLIS.2](https://github.com/microsoft/TRELLIS.2), with DINOv3
  features and a sparse decoder from TRELLIS-image-large. Their model and code
  licenses remain separate. No weights or vendor source trees are included.
- The compute environment also uses FlexGEMM, CuMesh, nvdiffrast, o-voxel,
  utils3d, PyTorch, Transformers, Diffusers, and trimesh. These are installed
  separately and retain their respective licenses.
- The nature map viewer references Three.js 0.180.0, OrbitControls, GLTFLoader,
  and MeshoptDecoder from jsDelivr. Browser asset compression uses
  [meshoptimizer](https://github.com/zeux/meshoptimizer) 0.25. These dependencies
  are referenced or installed separately, not vendored here.
- The source footage and extracted memory frames use the same Travel Intern
  attribution listed above. Generated outputs remain on the compute host and
  are excluded from this source-code update.

## Hong Kong city travel sample

“Hong Kong Trams, September 2009” by michaelinlondon is licensed under
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
[Source and license record](https://commons.wikimedia.org/wiki/File:Hong_Kong_Trams,_September_2009-UKNqZzl2cu8.webm).
Frames at 50, 190, and 435 seconds are extracted for the demonstration.
Reference frames are transformed into stylized building and tram meshes; the
street layout, illustrative pedestrians, and alternate lighting are added.
This attribution does not imply endorsement by the creator.
