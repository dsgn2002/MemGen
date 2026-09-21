"""Build a personalized digital souvenir from Kenney CC0 rocket modules."""
from pathlib import Path
import argparse, json
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser(); p.add_argument('--name', default='HKUST VISITOR'); args=p.parse_args()
out=ROOT/'output';out.mkdir(exist_ok=True)
scene=trimesh.Scene(); pieces=[]
navy=[20,39,64,255]; gold=[238,182,78,255]
def add(m,name,color=None):
 if color is not None: m.visual=trimesh.visual.ColorVisuals(mesh=m,face_colors=color)
 elif m.visual.kind=='texture': m.visual=trimesh.visual.ColorVisuals(mesh=m,face_colors=m.visual.material.main_color)
 scene.add_geometry(m,node_name=name,geom_name=name);pieces.append(m)
def box(size,pos,name,color):
 m=trimesh.creation.box(size);m.apply_translation(pos);add(m,name,color)
# Imported modules use Y up; work in Z up and millimetres.
z=13
for name in ['rocket_baseA','rocket_fuelB','rocket_topA']:
 src=trimesh.load(ROOT/'assets/kenney/Models/GLTF format'/f'{name}.glb',force='scene')
 meshes=src.dump()
 bounds=src.bounds; center=(bounds[0]+bounds[1])/2
 for i,m in enumerate(meshes):
  v=m.vertices.copy();m.vertices=np.column_stack(((v[:,0]-center[0])*23,-(v[:,2]-center[2])*23,(v[:,1]-bounds[0,1])*23+z))
  add(m,f'{name}_{i}')
 z+=(bounds[1,1]-bounds[0,1])*23-.25
base=trimesh.creation.cylinder(radius=38,height=10,sections=96);base.apply_translation([0,0,5]);add(base,'navy_plinth',navy)
ring=trimesh.creation.cylinder(radius=38.3,height=1.6,sections=96);ring.apply_translation([0,0,10]);add(ring,'gold_rim',gold)
pad=trimesh.creation.cylinder(radius=29,height=3,sections=96);pad.apply_translation([0,0,11.5]);add(pad,'launch_pad',navy)
box([62,5,16],[0,-38.5,12],'nameplate',navy)
def lettering(text,width,z0):
 path=TextPath((0,0),text,size=10,prop=FontProperties(family='DejaVu Sans',weight='bold'))
 shape=Polygon()
 for coords in path.to_polygons():
  poly=Polygon(coords)
  if poly.is_valid: shape=shape.symmetric_difference(poly)
 minx,miny,maxx,maxy=shape.bounds;scale=width/(maxx-minx)
 polys=list(shape.geoms) if hasattr(shape,'geoms') else [shape]
 for i,poly in enumerate(polys):
  m=trimesh.creation.extrude_polygon(poly,height=.65)
  v=m.vertices.copy();m.vertices=np.column_stack(((v[:,0]-(minx+maxx)/2)*scale,-41-v[:,2],(v[:,1]-miny)*scale+z0))
  add(m,f'text_{text}_{i}',gold)
lettering(args.name.upper()[:24],53,12)
lettering('CAMPUS EXPLORER',43,6)
# GLB uses Y up and metres.
glb_scene=scene.copy(); transform=trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0]);transform[:3,:3]*=.001
glb_scene.apply_transform(transform);glb_scene.export(out/'personalized-rocket.glb')
# STL is an assembly preview, not a certified printable solid.
trimesh.util.concatenate(pieces).export(out/'personalized-rocket-assembly.stl')
# Orthographic software renderer with a depth buffer for intersecting assembly parts.
from PIL import Image, ImageDraw, ImageFont
W=H=1400
canvas=np.full((H,W,3),[237,241,245],dtype=np.uint8);depth=np.full((H,W),-np.inf)
view=np.array([.28,-.92,.28]);view/=np.linalg.norm(view)
right=np.cross([0,0,1],view);right/=np.linalg.norm(right);up=np.cross(view,right)
for m in pieces:
 v=np.asarray(m.vertices)-[0,0,43]
 proj=np.column_stack((v@right*10+700,-v@up*10+770,v@view))
 for ids,normal,color in zip(m.faces,m.face_normals,m.visual.face_colors):
  t=proj[ids];lo=np.maximum(np.floor(t[:,:2].min(0)).astype(int),0);hi=np.minimum(np.ceil(t[:,:2].max(0)).astype(int),[W-1,H-1])
  if np.any(hi<lo):continue
  x,y=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5)
  a,b,c=t;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
  if abs(den)<1e-8:continue
  u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den
  v2=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den
  w=1-u-v2;zbuf=u*a[2]+v2*b[2]+w*c[2]
  region=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1];mask=(u>=0)&(v2>=0)&(w>=0)&(zbuf>region+1e-5)
  region[mask]=zbuf[mask]
  shade=.62+.38*max(0,float(normal@np.array([-.3,-.5,.8])))
  canvas[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=np.asarray(color[:3])*shade
im=Image.fromarray(canvas);draw=ImageDraw.Draw(im)
from matplotlib.font_manager import findfont
font=findfont(FontProperties(family='DejaVu Sans',weight='bold'))
draw.text((80,75),'CAMPUS EXPLORER',font=ImageFont.truetype(font,48),fill='#142740')
draw.text((80,145),'A personalized keepsake / Kenney CC0 mesh',font=ImageFont.truetype(font,23),fill='#54677a')
draw.text((80,1300),'HKUST VISITOR / SAMPLE 001',font=ImageFont.truetype(font,22),fill='#54677a')
im.save(out/'preview.png')
loaded=trimesh.load(out/'personalized-rocket.glb',force='scene')
report={'name':args.name,'source':'https://kenney.nl/assets/space-kit','license':'CC0','geometry_count':len(loaded.geometry),'triangles':sum(len(m.faces) for m in loaded.geometry.values()),'dimensions_mm':(scene.bounds[1]-scene.bounds[0]).tolist(),'all_vertices_finite':all(np.isfinite(m.vertices).all() for m in loaded.geometry.values()),'note':'Digital assembly. STL requires union/repair and printability validation.'}
(out/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
