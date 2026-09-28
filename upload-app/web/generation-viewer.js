import * as THREE from '../viewer-build/node_modules/three/build/three.module.js';
import {OrbitControls} from '../viewer-build/node_modules/three/examples/jsm/controls/OrbitControls.js';
import {GLTFLoader} from '../viewer-build/node_modules/three/examples/jsm/loaders/GLTFLoader.js';
import {MeshoptDecoder} from '../viewer-build/node_modules/three/examples/jsm/libs/meshopt_decoder.module.js';
import {createRefinedScene} from './refined-scenes.js';
const $=id=>document.getElementById(id), params=new URLSearchParams(location.search),project=params.get('project'),generation=params.get('generation');
const base=`/api/projects/${encodeURIComponent(project)}/generations/${encodeURIComponent(generation)}`;
$('back').href='/#'+encodeURIComponent(project);
(async()=>{
 const response=await fetch(base+'/result');if(!response.ok)throw Error('Open your trip and sign in to view this memory.');
 const result=await response.json(),scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(40,1,.01,100);
 const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.outputColorSpace=THREE.SRGBColorSpace;
 $('viewport').append(renderer.domElement);const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.minDistance=.7;controls.maxDistance=12;
 const hemi=new THREE.HemisphereLight(0xcde5ff,0x4f4633,2.5),sun=new THREE.DirectionalLight(0xffffff,4);sun.position.set(3,5,4);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);sun.shadow.camera.left=-2;sun.shadow.camera.right=2;sun.shadow.camera.top=3;sun.shadow.camera.bottom=-1;sun.shadow.bias=-.001;scene.add(hemi,sun);
 const rim=new THREE.PointLight(0xffb957,12,10);rim.position.set(-2,1,1);scene.add(rim);
 const floor=new THREE.Mesh(new THREE.CylinderGeometry(1.4,1.5,.07,64),new THREE.MeshStandardMaterial({color:0x355d4b,roughness:.8}));floor.receiveShadow=true;floor.position.y=-.035;scene.add(floor);
 const stars=new THREE.BufferGeometry(),positions=[];for(let i=0;i<450;i++){const a=i*2.399963;const h=1+(i%89)/13;positions.push(Math.cos(a)*8,h,Math.sin(a)*8);}stars.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));const skyStars=new THREE.Points(stars,new THREE.PointsMaterial({color:0xe5efff,size:.025}));scene.add(skyStars);
 function lighting(){const mode=$('lighting').value;scene.background=new THREE.Color(mode==='night'?0x091627:mode==='sunset'?0xc78157:0xbad7df);hemi.intensity=mode==='night'?1.3:2.5;sun.color.set(mode==='sunset'?0xffb66d:mode==='night'?0x93b4ff:0xffffff);sun.intensity=mode==='night'?2:4;rim.intensity=mode==='night'?18:mode==='sunset'?10:2;skyStars.visible=mode==='night';} $('lighting').value=result.lighting;$('lighting').onchange=lighting;lighting();
 function reset(){camera.position.set(2.6,1.7,2.7);controls.target.set(0,.65,0);controls.update();}reset();$('reset').onclick=reset;
 const loader=new GLTFLoader().setMeshoptDecoder(MeshoptDecoder),cache=new Map();let current=null,request=0,selected=null;
 let animated=null,clock=new THREE.Clock();
 $('animation').checked=!matchMedia('(prefers-reduced-motion: reduce)').matches;
 const assetURL=name=>base+'/assets/'+encodeURIComponent(name);
 async function show(asset){
  const ticket=++request;selected=asset;
  const refined=Boolean(asset.presentation)&&$('representation').value==='refined';
  $('representation-row').hidden=!asset.presentation;
  $('animation-row').hidden=!refined;
  $('scene-note').textContent=refined?'Curated scene assembly: generic characters and clean objects. Placement and appearance are creative choices.':'Source-guided generated mesh. Hidden surfaces are inferred; likeness and geometry may differ from the original.';
  $('status').textContent=refined?'Loading animated scene…':'Loading original mesh…';
  const key=asset.id+(refined?':refined':':original');let entry=cache.get(key);
  if(!entry){
   if(refined)entry=await createRefinedScene(asset.presentation.preset,loader);
   else{
    const gltf=await loader.loadAsync(assetURL(asset.mesh)),mesh=gltf.scene;
    const box=new THREE.Box3().setFromObject(mesh),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3()),scale=1.7/Math.max(size.x,size.y,size.z);
    mesh.position.sub(center);mesh.scale.setScalar(scale);mesh.position.multiplyScalar(scale);mesh.position.y+=size.y*scale/2;
    entry={root:mesh,characters:[],sways:[]};
   }
   cache.set(key,entry);
  }
  if(ticket!==request)return;
  if(current)scene.remove(current);current=entry.root;animated=refined?entry:null;scene.add(current);
  $('source').src=assetURL(asset.source);$('design').src=assetURL(asset.design);$('download').href=assetURL(asset.mesh);$('download').download=asset.mesh;
  $('download').textContent=refined?'Download original generated mesh':'Download 3D model';
  for(const b of $('moments').children)b.setAttribute('aria-pressed',String(b.dataset.id===asset.id));
  $('status').textContent=refined?'Refined 3D scene ready':'3D memory ready';
  window.memgenViewer={loaded:asset.id,representation:refined?'refined':'original',vertices:0,texturedMeshes:0,characters:entry.characters,lanterns:entry.sways.length,animationTime:0};
  current.traverse(o=>{if(o.isMesh){window.memgenViewer.vertices+=o.geometry.attributes.position.count;const materials=Array.isArray(o.material)?o.material:[o.material];if(materials.some(m=>m.map?.image))window.memgenViewer.texturedMeshes++;}});
 }
 $('representation').onchange=()=>show(selected).catch(fail);
 for(const [i,asset] of result.assets.entries()){
  const b=document.createElement('button'),label=asset.label.split(';').map(s=>s.trim()).filter(s=>s&&s.toLowerCase()!=='none').join(' · ');
  b.textContent=`Moment ${i+1} · ${label}`;b.dataset.id=asset.id;b.onclick=()=>show(asset).catch(fail);$('moments').append(b);
 }
 const t=result.timing;$('timing').textContent=`Generation: ${(t.generation_seconds/60).toFixed(1)} min. First analysis to completed generation: ${(t.first_analysis_to_generation_seconds/60).toFixed(1)} min, including retries, fixes and review time.`;
 new ResizeObserver(()=>{const {clientWidth:w,clientHeight:h}=$('viewport');renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();}).observe($('viewport'));
 renderer.setAnimationLoop(()=>{const delta=Math.min(clock.getDelta(),.05);if(animated&&$('animation').checked){animated.update(delta);if(window.memgenViewer)window.memgenViewer.animationTime=animated.time;}controls.update();renderer.render(scene,camera);});await show(result.assets[0]);
})().catch(fail);
function fail(error){$('status').textContent=error.message;console.error(error);}
