"""Pack Quaternius embedded glTF as GLB, retaining only the idle animation.

Usage: python pack_characters.py INPUT.gltf OUTPUT.glb
The source files and license provenance are documented in web/characters/README.md.
"""
import base64
import json
import struct
import sys
from pathlib import Path

source, target = map(Path, sys.argv[1:])
g = json.loads(source.read_text())
g['animations'] = [a for a in g['animations'] if a['name'] == 'Idle']
if len(g['animations']) != 1:
    raise ValueError('Expected one Idle animation')
references = []
for mesh in g['meshes']:
    for primitive in mesh['primitives']:
        references.extend((primitive['attributes'], k) for k in primitive['attributes'])
        if 'indices' in primitive:
            references.append((primitive, 'indices'))
        for morph in primitive.get('targets', []):
            references.extend((morph, k) for k in morph)
for skin in g.get('skins', []):
    if 'inverseBindMatrices' in skin:
        references.append((skin, 'inverseBindMatrices'))
for animation in g['animations']:
    for sampler in animation['samplers']:
        references.extend([(sampler, 'input'), (sampler, 'output')])
used = sorted({obj[key] for obj,key in references})
remap = {old:i for i,old in enumerate(used)}
for obj,key in references:
    obj[key] = remap[obj[key]]
g['accessors'] = [g['accessors'][i] for i in used]
views = sorted({a['bufferView'] for a in g['accessors']})
if any('sparse' in a for a in g['accessors']) or g.get('images'):
    raise ValueError('This packer expects dense, untextured source characters')
remap = {old:i for i,old in enumerate(views)}
for a in g['accessors']:
    a['bufferView'] = remap[a['bufferView']]
g['bufferViews'] = [g['bufferViews'][i] for i in views]
buffers = []
for b in g['buffers']:
    if not b['uri'].startswith('data:application/octet-stream;base64,'):
        raise ValueError('Expected embedded source data')
    buffers.append(base64.b64decode(b['uri'].split(',',1)[1]))
out = bytearray()
for v in g['bufferViews']:
    out.extend(b'\0'*(-len(out)%4))
    offset = v.get('byteOffset',0)
    data = buffers[v['buffer']][offset:offset+v['byteLength']]
    v.update(buffer=0, byteOffset=len(out))
    out.extend(data)
g['buffers'] = [{'byteLength':len(out)}]
out.extend(b'\0'*(-len(out)%4))
js = json.dumps(g,separators=(',',':')).encode()
js += b' '*(-len(js)%4)
target.write_bytes(struct.pack('<III',0x46546c67,2,28+len(js)+len(out))+
                  struct.pack('<II',len(js),0x4e4f534a)+js+
                  struct.pack('<II',len(out),0x004e4942)+out)
print(target.name, target.stat().st_size, 'bytes, Idle animation')
