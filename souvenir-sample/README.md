# Campus Explorer souvenir sample

A reusable mesh customization prototype: Kenney rocket modules, navy/gold plinth, and extruded visitor name. No AI inference has been run for this sample.

Source: https://kenney.nl/assets/space-kit
License: CC0. Original license is in assets/kenney/License.txt.
Modules: rocket_baseA, rocket_fuelB, rocket_topA.

## Rebuild

Create an isolated Python environment, install requirements.txt, then run:

    python build_sample.py --name "YOUR NAME"

Output GLB uses metres and Y-up. Output STL uses millimetres and Z-up.
The STL is an overlapping mesh assembly and needs union/repair and thickness checks before printing. GLB is the primary digital souvenir.

preview.png is a geometry preview. viewer.html is interactive and loads the Google model-viewer library from a CDN, requiring internet access. The mesh itself is embedded in the page.
