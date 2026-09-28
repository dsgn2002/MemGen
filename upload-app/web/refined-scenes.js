// Curated presentation presets. These are editable assemblies, not reconstructions.
import * as THREE from '../viewer-build/node_modules/three/build/three.module.js';
import {clone} from '../viewer-build/node_modules/three/examples/jsm/utils/SkeletonUtils.js';
const material=(color,extra={})=>new THREE.MeshStandardMaterial({color,roughness:.65,...extra});
const wood=material(0x71462c),trim=material(0x243c37),cream=material(0xe7dac2),brass=material(0xbc934a,{metalness:.55,roughness:.35});
function mesh(parent,geometry,mat,x=0,y=0,z=0){const o=new THREE.Mesh(geometry,mat);o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;parent.add(o);return o;}
function box(p,w,h,d,mat,x,y,z){return mesh(p,new THREE.BoxGeometry(w,h,d),mat,x,y,z);}
function cylinder(p,r,h,mat,x,y,z){return mesh(p,new THREE.CylinderGeometry(r,r,h,32),mat,x,y,z);}
function ball(p,r,mat,x,y,z,scale=[1,1,1]){const o=mesh(p,new THREE.SphereGeometry(r,24,16),mat,x,y,z);o.scale.fromArray(scale);return o;}
function label(p,text,w,h,x,y,z){const c=document.createElement('canvas');c.width=1024;c.height=256;const g=c.getContext('2d');g.fillStyle='#203f37';g.fillRect(0,0,c.width,c.height);g.fillStyle='#efd6a0';g.font='bold 94px serif';g.textAlign='center';g.textBaseline='middle';g.fillText(text,512,128,940);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;return mesh(p,new THREE.PlaneGeometry(w,h),material(0xffffff,{map:t,roughness:.8}),x,y,z);}
function table(p,x,z){cylinder(p,.58,.07,wood,x,.78,z);cylinder(p,.075,.68,brass,x,.4,z);cylinder(p,.24,.06,trim,x,.08,z);for(let i=0;i<3;i++){const a=i*Math.PI*2/3;const px=x+Math.sin(a)*.34,pz=z+Math.cos(a)*.34;cylinder(p,.12,.018,cream,px,.827,pz);ball(p,.07,material(0xb97533),px,.86,pz,[1,.5,1]);cylinder(p,.04,.085,cream,px+.12,.86,pz+.04);}}
const templates=new Map();
async function character(loader,kind){if(!templates.has(kind))templates.set(kind,loader.loadAsync('/static/characters/'+kind+'.glb').catch(e=>{templates.delete(kind);throw e;}));return templates.get(kind);}
export async function createRefinedScene(preset,loader){
 const root=new THREE.Group();root.name=preset;const mixers=[],sways=[],characters=[];let elapsed=0;
 if(preset==='dining-characters-v1'){
  box(root,6,.16,3.8,wood,0,.02,0);for(let i=0;i<15;i++)box(root,.018,.006,3.7,trim,-2.8+i*.4,.104,0);
  box(root,6,3,.12,cream,0,1.6,-1.8);box(root,6,.18,.25,trim,0,3.14,-1.75);
  for(const x of [-2.87,2.87]){box(root,.22,3.1,.28,cream,x,1.63,-1.2);box(root,.26,.08,.34,brass,x,2.9,-1.2);}
  box(root,5.4,.52,.22,trim,0,2.72,-1.61);label(root,'茶 餐 廳  ·  TEA HOUSE',4.9,.42,0,2.72,-1.486);
  for(const x of [-1.92,1.92]){box(root,1.45,1.42,.06,trim,x,1.52,-1.705);box(root,1.27,1.26,.02,material(0xb5cfc4,{roughness:.25}),x,1.52,-1.663);for(let i=-1;i<=1;i++)box(root,.025,1.26,.035,wood,x+i*.4,1.52,-1.64);box(root,1.27,.04,.035,wood,x,1.5,-1.64);}
  box(root,.95,1.94,.08,wood,0,1.13,-1.69);box(root,.78,1.65,.03,trim,0,1.23,-1.64);cylinder(root,.035,.07,brass,.3,1.12,-1.57).rotation.x=Math.PI/2;
  table(root,-1.37,-.3);table(root,1.36,-.28);
  for(const x of [-2.65,2.65]){cylinder(root,.2,.28,material(0x994d30),x,.25,.95);for(let i=0;i<8;i++){const leaf=ball(root,.25,material(0x507855),x+Math.sin(i*2.4)*.16,.59+(i%3)*.13,.95+Math.cos(i*2.4)*.15,[.3,1,.65]);leaf.rotation.z=Math.sin(i)*.65;}}
  // Generic adults placed around cafe tables; count and appearance are creative choices.
  const placements=[['male',-2.07,.18,.8],['female',-.67,.10,-.85],['female',2.09,.08,-.75],['male',.62,.15,.9]];
  for(let i=0;i<placements.length;i++){
   const [kind,x,z,angle]=placements[i],template=await character(loader,kind),actor=clone(template.scene),holder=new THREE.Group();
   actor.updateMatrixWorld(true);const b=new THREE.Box3().setFromObject(actor),size=b.getSize(new THREE.Vector3()),center=b.getCenter(new THREE.Vector3());const scale=1.72/size.y;
   actor.scale.multiplyScalar(scale);actor.position.set(-center.x*scale,-b.min.y*scale,-center.z*scale);holder.add(actor);holder.position.set(x,.105,z);holder.rotation.y=angle;root.add(holder);
   actor.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});
   const idle=template.animations.find(c=>/^idle$/i.test(c.name))||template.animations.find(c=>/idle/i.test(c.name));
   if(!idle)throw Error('The character asset has no idle animation.');
   const mixer=new THREE.AnimationMixer(actor);mixer.clipAction(idle).play();mixer.update(i*.47);mixers.push(mixer);characters.push({kind,clip:idle.name});
  }
 }else if(preset==='lantern-display-v1'){
  box(root,5.8,.16,3.2,wood,0,.02,0);
  for(const x of [-2.65,2.65]){cylinder(root,.06,3.85,brass,x,2.02,-.4);box(root,.5,.13,.5,trim,x,.15,-.4);}
  for(const y of [2.65,3.87])box(root,5.5,.085,.085,wood,0,y,-.4);
  const colors=[0xe74435,0xffb626,0x43bebe,0xf084ad,0x78b957,0xf07830];
  for(let row=0;row<2;row++)for(let col=0;col<5;col++){
   const i=row*5+col,x=-2.16+col*1.08,y=row?2.62:3.84,pivot=new THREE.Group();pivot.position.set(x,y,-.36+(col%2)*.28);root.add(pivot);
   const cord=.25+(i%3)*.06;cylinder(pivot,.009,cord,trim,0,-cord/2,0);
   const body=new THREE.Group();body.position.y=-cord-.31;pivot.add(body);const mat=material(colors[i%colors.length],{emissive:colors[i%colors.length],emissiveIntensity:.24,roughness:.5,side:THREE.DoubleSide});
   if(i%3===1){
    ball(body,.31,mat,0,0,0,[1.25,.85,.7]);const tail=new THREE.Mesh(new THREE.ConeGeometry(.25,.32,3),mat);tail.rotation.z=-Math.PI/2;tail.position.x=-.47;body.add(tail);
    for(const side of [-1,1]){ball(body,.065,cream,.22,.07,side*.185);ball(body,.032,trim,.247,.076,side*.232);}
    const fin=mesh(body,new THREE.ConeGeometry(.17,.22,3),mat,-.07,.24,0);fin.scale.z=.2;
    for(let j=0;j<4;j++){const ring=mesh(body,new THREE.TorusGeometry(.215-j*.015,.008,6,32),brass,-.04-j*.07,0,0);ring.rotation.y=Math.PI/2;}
   }else{
    ball(body,.31,mat,0,0,0,[1,i%2?1.13:.86,1]);
    for(let j=0;j<12;j++){const points=[];for(let k=0;k<=24;k++){const t=Math.PI*k/24,ang=j*Math.PI/6;points.push(new THREE.Vector3(.313*Math.sin(t)*Math.cos(ang),.313*Math.cos(t)*(i%2?1.13:.86),.313*Math.sin(t)*Math.sin(ang)));}mesh(body,new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points),24,.005,4,false),brass);}
    cylinder(body,.1,.035,brass,0,.29*(i%2?1.13:.86),0);cylinder(body,.09,.03,brass,0,-.29*(i%2?1.13:.86),0);
   }
   for(let j=0;j<5;j++)cylinder(body,.006,.24,mat,(j-2)*.018,-.44,0);sways.push({pivot,phase:i*1.3});
  }
  box(root,5.2,.12,.78,wood,0,.63,-.55);for(const x of [-2.3,2.3])box(root,.1,.55,.58,trim,x,.34,-.55);
  label(root,'中 秋  ·  LANTERNS',2.7,.33,0,.45,-.145);
 }else throw Error('Unsupported scene refinement.');
 root.updateMatrixWorld(true);const bounds=new THREE.Box3().setFromObject(root),size=bounds.getSize(new THREE.Vector3()),center=bounds.getCenter(new THREE.Vector3()),scale=1.7/Math.max(size.x,size.y,size.z);root.scale.setScalar(scale);root.position.set(-center.x*scale,-bounds.min.y*scale,-center.z*scale);
 return {root,characters,mixers,sways,update(delta){elapsed+=delta;for(const m of mixers)m.update(delta);for(const s of sways){s.pivot.rotation.z=Math.sin(elapsed*.8+s.phase)*.06;s.pivot.rotation.x=Math.sin(elapsed*.6+s.phase)*.025;}},get time(){return elapsed;}};
}
