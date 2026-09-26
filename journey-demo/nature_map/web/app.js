import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {MeshoptDecoder} from 'three/addons/libs/meshopt_decoder.module.js';
import {EffectComposer} from 'three/addons/postprocessing/EffectComposer.js';
import {RenderPass} from 'three/addons/postprocessing/RenderPass.js';
import {UnrealBloomPass} from 'three/addons/postprocessing/UnrealBloomPass.js';
import {OutputPass} from 'three/addons/postprocessing/OutputPass.js';

const $=id=>document.getElementById(id), city=new URLSearchParams(location.search).get('scene')==='city';
const sourceCity='https://commons.wikimedia.org/wiki/File:Hong_Kong_Trams,_September_2009-UKNqZzl2cu8.webm';
const memories=city?[
 {image:'city/frame-50.jpg',text:'0:50 · A double-decker tram travels between dense apartment blocks and shopfronts.'},
 {image:'city/frame-190.jpg',text:'3:10 · Tram tracks thread through the Hong Kong streetscape.'},
 {image:'city/frame-435.jpg',text:'7:15 · A pale blue double-decker tram rounds a street corner.'}
]:[
 {image:'memories/frame-60.jpg',text:'1:00 · Three companions aboard the green-canopy boat: white shirt, dark sleeveless top, and orange jacket.'},
 {image:'memories/frame-80.jpg',text:'1:20 · High Island Reservoir, with stonework between the hills and turquoise water.'},
 {image:'memories/frame-98.jpg',text:'1:38 · A traveler on the MacLehose coastal path above the bay.'}
];
$(city?'city-link':'coast-link').setAttribute('aria-current','page');
if(city){$('chapter').textContent='02 / HONG KONG ISLAND';$('title').textContent='A city in motion.';$('focus').textContent='Follow the tram';$('canopy-control').hidden=true;}
$('about').textContent=city?'A stylized recomposition of a 2009 Hong Kong tram-travel video. The buildings and tram were generated from source frames. Street layout, lights, and illustrative pedestrians are composed for this demo; this is not a measured reconstruction.':'Three separate reference-conditioned passenger meshes restore the visible group aboard the boat. Their clothing is approximate, and their faces are stylized. The landscape is an artistic composition. Open canopy view removes the roof for inspection.';
$('credits').innerHTML=city?`Source: <a href="${sourceCity}" target="_blank" rel="noopener">Hong Kong Trams, September 2009</a> by michaelinlondon, <a href="https://creativecommons.org/licenses/by/3.0/" target="_blank" rel="noopener">CC BY 3.0</a>. Frames extracted and transformed into stylized assets.`:'Source: <a href="https://www.youtube.com/watch?v=9jtnoejpLcU" target="_blank" rel="noopener">The Travel Intern · Hong Kong Outdoor Adventure</a>. Source footage and generated assets retain their respective rights.';
let selected=0;
function selectMemory(i){selected=i;$('memory-image').src=memories[i].image;$('memory-image').alt=memories[i].text;$('memory-caption').textContent=memories[i].text;document.querySelectorAll('[data-memory]').forEach(b=>b.setAttribute('aria-pressed',Number(b.dataset.memory)===i));}
memories.forEach((m,i)=>{const b=document.createElement('button');b.textContent=String(i+1).padStart(2,'0');b.dataset.memory=i;b.ariaLabel=m.text;b.onclick=()=>selectMemory(i);$('memories').appendChild(b)});selectMemory(0);

const scene=new THREE.Scene();scene.fog=new THREE.Fog('#c4e4df',35,100);
const renderer=new THREE.WebGLRenderer({canvas:$('canvas'),antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.7));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.localClippingEnabled=true;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;
const camera=new THREE.PerspectiveCamera(42,1,.05,180);const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.minDistance=3;controls.maxDistance=48;controls.maxPolarAngle=Math.PI*.49;
const root=new THREE.Group();scene.add(root);const hemi=new THREE.HemisphereLight('#dcefff','#577b69',2);scene.add(hemi);const sun=new THREE.DirectionalLight('#fff0d3',3);sun.position.set(-12,20,10);sun.castShadow=true;sun.shadow.mapSize.set(innerWidth<700?1024:2048,innerWidth<700?1024:2048);Object.assign(sun.shadow.camera,{left:-22,right:22,top:22,bottom:-22,near:.5,far:90});sun.shadow.bias=-.0003;scene.add(sun);const fill=new THREE.DirectionalLight('#c8e3ef',.7);fill.position.set(15,10,20);scene.add(fill);
const composer=new EffectComposer(renderer);composer.addPass(new RenderPass(scene,camera));const bloom=new UnrealBloomPass(new THREE.Vector2(1,1),.25,.65,1.1);composer.addPass(bloom);composer.addPass(new OutputPass());
const skyUniforms={top:{value:new THREE.Color('#419bc7')},horizon:{value:new THREE.Color('#d7eee2')},sunColor:{value:new THREE.Color('#fff8d8')},sunDirection:{value:new THREE.Vector3(-.6,.7,-.3).normalize()},disc:{value:1}};
const sky=new THREE.Mesh(new THREE.SphereGeometry(100,32,16),new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,uniforms:skyUniforms,vertexShader:'varying vec3 vDirection; void main(){vDirection=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',fragmentShader:'varying vec3 vDirection;uniform vec3 top,horizon,sunColor,sunDirection;uniform float disc;void main(){vec3 d=normalize(vDirection);float h=pow(max(d.y,0.),.6);vec3 c=mix(horizon,top,clamp(h,0.,1.));float s=max(dot(d,sunDirection),0.);c+=sunColor*(smoothstep(.99965,.9999,s)*2.+pow(s,90.)*.08)*disc;gl_FragColor=vec4(c,1.);#include <tonemapping_fragment>\n#include <colorspace_fragment>}',toneMapped:true}));sky.material.fragmentShader=sky.material.fragmentShader.replace(';#include',';\n#include');scene.add(sky);
const starGeo=new THREE.BufferGeometry(),starCoords=[];let seed=1926;function rand(){seed=(1664525*seed+1013904223)>>>0;return seed/4294967296}for(let i=0;i<900;i++){const a=rand()*Math.PI*2,y=.015+rand()*.94,r=Math.sqrt(1-y*y);starCoords.push(Math.cos(a)*r*85,y*85,Math.sin(a)*r*85)}starGeo.setAttribute('position',new THREE.Float32BufferAttribute(starCoords,3));const stars=new THREE.Points(starGeo,new THREE.PointsMaterial({color:'#dce7ff',size:.28,transparent:true,opacity:0,depthWrite:false}));scene.add(stars);
const clock=new THREE.Clock(),glb=new GLTFLoader().setMeshoptDecoder(MeshoptDecoder),lamps=[],glows=[],assetNames=[],passengers=[],passengerPositions=[];
let loading=true,playing=!matchMedia('(prefers-reduced-motion: reduce)').matches,elapsed=0,preset='day',intensity=1,boat,tram,water,follow=false,triangles=0,loadError=null;
const roofPlane=new THREE.Plane(new THREE.Vector3(0,-1,0),1.4);
function std(color,extra={}){return new THREE.MeshStandardMaterial({color,roughness:.7,...extra})}
function box(w,h,d,material,x=0,y=0,z=0,parent=root){const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m}
async function model(name,size,fit='max'){
 const loaded=await glb.loadAsync(name+'.web.glb'),inner=loaded.scene,bounds=new THREE.Box3().setFromObject(inner),dims=bounds.getSize(new THREE.Vector3()),center=bounds.getCenter(new THREE.Vector3());
 inner.position.sub(new THREE.Vector3(center.x,bounds.min.y,center.z));const scaled=new THREE.Group();scaled.add(inner);const scale=size/(fit==='height'?dims.y:Math.max(dims.x,dims.y,dims.z));scaled.scale.setScalar(scale);const result=new THREE.Group();result.add(scaled);result.userData.dimensions=dims.multiplyScalar(scale);result.userData.name=name;
 inner.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;triangles+=(o.geometry.index?.count||o.geometry.attributes.position.count)/3;}});assetNames.push(name);return result;
}
function glowSphere(parent,position,color,size=.055,power=3){const material=std(color,{emissive:color,emissiveIntensity:0});const globe=new THREE.Mesh(new THREE.SphereGeometry(size,12,8),material);globe.position.fromArray(position);parent.add(globe);glows.push(material);const light=new THREE.PointLight(color,0,4,2);light.position.copy(globe.position);parent.add(light);lamps.push({light,power});return globe;}
const presets={day:{top:'#368aba',horizon:'#d0e8df',sun:'#fff4d9',ground:'#70927b',position:[-12,24,9],sunPower:3,ambient:2,exposure:1.08,bloom:.2,water:'#238d9e',stars:0},sunset:{top:'#433361',horizon:'#ffa466',sun:'#ffb663',ground:'#675367',position:[-20,2,-26],sunPower:4,ambient:1.1,exposure:1.08,bloom:.55,water:'#345078',stars:0},night:{top:'#020719',horizon:'#182941',sun:'#9ebeff',ground:'#243951',position:[-20,1,-26],sunPower:.9,ambient:.8,exposure:1,bloom:.8,water:'#06162e',stars:.85}};
function lighting(name){preset=name;const p=presets[name];document.body.dataset.light=name;document.querySelectorAll('[data-preset]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.preset===name));skyUniforms.top.value.set(p.top);skyUniforms.horizon.value.set(p.horizon);skyUniforms.sunColor.value.set(p.sun);skyUniforms.sunDirection.value.fromArray(p.position).normalize();skyUniforms.disc.value=name==='night'?.5:1;scene.fog.color.set(p.horizon);sun.color.set(p.sun);sun.position.fromArray(p.position);sun.intensity=p.sunPower*intensity;fill.color.set(name==='night'?'#88aef0':name==='sunset'?'#e9c1a8':'#d5efff');fill.intensity=(name==='night'?1.1:name==='sunset'?1.3:.7)*intensity;hemi.color.set(name==='night'?'#a8c0e4':'#e2f2ff');hemi.groundColor.set(p.ground);hemi.intensity=p.ambient*intensity;renderer.toneMappingExposure=p.exposure;stars.material.opacity=p.stars;bloom.strength=p.bloom;lamps.forEach(({light,power})=>light.intensity=name==='night'?power*intensity:name==='sunset'?power*.4*intensity:0);glows.forEach(m=>m.emissiveIntensity=name==='night'?3*intensity:name==='sunset'?1.2*intensity:0);if(water){water.material.uniforms.base.value.set(p.water);water.material.uniforms.horizon.value.set(p.horizon);water.material.uniforms.sunColor.value.set(p.sun);water.material.uniforms.sunDirection.value.fromArray(p.position).normalize();water.material.uniforms.night.value=name==='night'?1:0;}}
function makeWater(){water=new THREE.Mesh(new THREE.PlaneGeometry(2000,2000,100,100),new THREE.ShaderMaterial({uniforms:{time:{value:0},base:{value:new THREE.Color()},horizon:{value:new THREE.Color()},sunColor:{value:new THREE.Color()},sunDirection:{value:new THREE.Vector3()},night:{value:0}},vertexShader:'uniform float time;varying vec3 wp;void main(){vec3 p=position;p.z+=sin(p.x*.8+time)*.045+cos(p.y*.65+time*.8)*.035;vec4 w=modelMatrix*vec4(p,1.);wp=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}',fragmentShader:'uniform float time,night;uniform vec3 base,horizon,sunColor,sunDirection;varying vec3 wp;void main(){vec3 n=normalize(vec3(-.07*cos(wp.x*.8+time),1.,-.065*sin(wp.z*.65-time*.8)));vec3 v=normalize(cameraPosition-wp);float fres=pow(1.-max(dot(n,v),0.),3.);vec3 c=mix(base,horizon,fres*.75);vec3 r=reflect(-v,n);float shine=pow(max(dot(r,sunDirection),0.),95.);c+=sunColor*shine*(1.5-night*.5);float wave=sin(wp.x*2.8+sin(wp.z*1.7+time))*sin(wp.z*3.4-time);c+=vec3(.004)*(1.-night*.7)*wave;c=mix(c,horizon,smoothstep(30.,140.,length(wp-cameraPosition)));gl_FragColor=vec4(c,1.);\n#include <tonemapping_fragment>\n#include <colorspace_fragment>\n}'}));water.rotation.x=-Math.PI/2;water.position.y=-.12;scene.add(water);}
async function loadCoast(){
 makeWater();const coast=await model('coast',14);coast.position.y=-1.15;root.add(coast);$('load-text').textContent='Adding the boat and three companions…';
 const hiker=await model('traveler',1.35,'height');root.add(hiker);hiker.position.set(-3.5,1.5,0);coast.updateMatrixWorld(true);const ray=new THREE.Raycaster(new THREE.Vector3(-3.5,15,0),new THREE.Vector3(0,-1,0));const hit=ray.intersectObject(coast,true);if(hit.length)hiker.position.y=hit[0].point.y+.025;
 boat=await model('boat',4.2);boat.name='boat-with-three-passengers';root.add(boat);
 const plan=await fetch('scene-plan.json').then(r=>{if(!r.ok)throw new Error('Scene plan unavailable');return r.json()});
 if(plan.coast.passengers.length!==plan.coast.requirements.passenger_count)throw new Error('Passenger plan count mismatch');
 const poses=plan.coast.passengers.map(p=>p.position);
 for(const [i,name] of plan.coast.passengers.map(p=>p.asset).entries()){
  const person=await model(name,.86,'height');person.position.fromArray(poses[i]);person.rotation.y=.1;person.name=name;boat.add(person);passengers.push(person);passengerPositions.push(poses[i]);
 }
 boat.children[0].traverse(o=>{if(o.isMesh){o.material=o.material.clone();o.material.clipShadows=true;}});
 glowSphere(boat,[-.48,1.12,-.5],'#ffcb75',.065,2.5);glowSphere(boat,[.48,1.12,-.5],'#ffcb75',.065,2.5);
 boat.position.set(-8,-.38,6);boat.rotation.y=.2;
}
function makeLamp(x,z){const pole=std('#293b46',{metalness:.5});box(.07,3.4,.07,pole,x,1.7,z);box(.6,.06,.08,pole,x+(x<0?.25:-.25),3.4,z);glowSphere(root,[x+(x<0?.52:-.52),3.35,z],'#ffd890',.12,7);}
async function loadCity(){
 scene.fog.near=40;const base=box(18,.7,26,std('#263b47'),0,-.45,0);box(7,.12,25,std('#35434b',{roughness:.38}),0,-.04,0);for(const x of [-4.6,4.6])box(2.2,.2,25,std('#a5a49c'),x,.05,0);
 const rail=std('#738896',{metalness:.9,roughness:.22});for(const x of [-1.75,-.95,.95,1.75])box(.055,.035,24,rail,x,.045,0);
 const line=std('#edc850');for(let z=-11;z<=11;z+=2)box(.1,.018,.85,line,0,.035,z);for(let i=0;i<8;i++)box(.65,.02,1.8,std('#e4e4d7'),-2.5+i*.72,.04,8.6);
 $('load-text').textContent='Opening the Hong Kong shopfronts and double-decker tram…';const buildings=await model('city/city-buildings',10);
 for(const x of [-6.8,6.8])for(const z of [-5.4,5.4]){const row=buildings.clone(true);row.rotation.y=x<0?Math.PI/2:-Math.PI/2;row.position.set(x,.18,z);root.add(row);}
 tram=await model('city/city-tram',3.5);if(tram.userData.dimensions.x>tram.userData.dimensions.z)tram.children[0].rotation.y=Math.PI/2;root.add(tram);tram.position.set(-1.35,.035,0);glowSphere(tram,[-.27,.48,1.68],'#fff3bd',.075,4);glowSphere(tram,[.27,.48,1.68],'#fff3bd',.075,4);
 for(const x of [-3.8,3.8])for(const z of [-9,-3,3,9])makeLamp(x,z);
 for(const x of [-4.7,4.7])for(const [i,z] of [-8,-4,0,4,8].entries()){const m=std(['#f26a61','#55c9d6','#e4ba5b'][i%3],{emissive:['#ff4848','#36bdde','#ffb34b'][i%3],emissiveIntensity:0});box(.08,.35,1.1,m,x,1.9,z);glows.push(m);}
 const people=[];for(const name of ['passenger-white','passenger-dark','passenger-orange'])people.push(await model(name,.65,'height'));
 for(let i=0;i<12;i++){const p=people[i%3].clone(true);p.position.set((i%2?-1:1)*(3.65+(i%3)*.22),.16,-10+(i*1.7)%20);p.rotation.y=i%2?0:Math.PI;root.add(p);}
}
function reset(){follow=false;root.scale.setScalar(1);$('scale').value=1;$('scale-value').textContent='100%';camera.position.set(...(city?[15,22,28]:[19,9,24]));controls.target.set(0,city?2.5:1.4,0);camera.position.sub(controls.target).multiplyScalar(Math.max(1,1/camera.aspect)).add(controls.target);controls.update();}
function focusSubject(){follow=true;selectMemory(0);const target=city?tram:boat;if(target){const p=target.getWorldPosition(new THREE.Vector3());controls.target.copy(p).add(new THREE.Vector3(0,city?1.5:.85,0));camera.position.copy(p).add(new THREE.Vector3(city?3.1:4.2,city?3:2.4,city?6.2:5.6));controls.update();}}
$('focus').onclick=focusSubject;$('reset').onclick=reset;controls.addEventListener('start',()=>follow=false);
function motionLabel(){$('motion').textContent=playing?'Pause motion':'Play motion';$('motion').setAttribute('aria-pressed',playing)}$('motion').onclick=()=>{playing=!playing;motionLabel()};motionLabel();
document.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>lighting(b.dataset.preset));$('intensity').oninput=e=>{intensity=+e.target.value;$('intensity-value').textContent=Math.round(intensity*100)+'%';lighting(preset)};$('scale').oninput=e=>{root.scale.setScalar(+e.target.value);$('scale-value').textContent=Math.round(e.target.value*100)+'%'};
$('canopy').onchange=()=>{if(boat)boat.children[0].traverse(o=>{if(o.isMesh){o.material.clippingPlanes=$('canopy').checked?[roofPlane]:[];o.material.needsUpdate=true;}})};
function resize(){const w=$('stage').clientWidth,h=$('stage').clientHeight;renderer.setSize(w,h,false);composer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix()}new ResizeObserver(resize).observe($('stage'));resize();reset();lighting('day');
try{if(city)await loadCity();else await loadCoast();loading=false;$('loader').hidden=true;lighting('day')}catch(error){loadError=error.message;$('load-text').textContent='The scene could not load. Refresh to retry. '+error.message;console.error(error)}
let lastSubject=null;
function animate(){requestAnimationFrame(animate);const dt=Math.min(clock.getDelta(),.1);if(playing)elapsed+=dt;if(water)water.material.uniforms.time.value=elapsed;
 if(boat){boat.position.set(-8+Math.sin(elapsed*.06)*.9,-.38+Math.sin(elapsed*1.6)*.035,6+Math.cos(elapsed*.06)*.6);boat.rotation.y=.2+Math.sin(elapsed*.06)*.35;roofPlane.constant=(boat.position.y+1.35)*root.scale.y;}
 if(tram){tram.position.z=Math.sin(elapsed*.12)*8;}
 const subject=city?tram:boat;if(follow&&subject){const p=subject.getWorldPosition(new THREE.Vector3());if(lastSubject)camera.position.add(p.clone().sub(lastSubject));controls.target.copy(p).add(new THREE.Vector3(0,city?1.5:.85,0));lastSubject=p;}else lastSubject=null;
 controls.update();sky.position.copy(camera.position);stars.position.copy(camera.position);composer.render();}
animate();
window.travelSceneState=()=>({scene:city?'city':'coast',loading,error:loadError,preset,intensity,playing,time:elapsed,scale:root.scale.x,assets:assetNames,triangles,passengerCount:passengers.length,passengerPositions,attachedToBoat:passengers.every(p=>p.parent===boat),canopyOpen:$('canopy').checked,stars:stars.material.opacity,lights:lamps.map(l=>l.light.intensity),camera:camera.position.toArray(),selectedMemory:selected,subjectPosition:(city?tram:boat)?.position.toArray(),sunIntensity:sun.intensity,illustrativePedestrians:city?12:0});
