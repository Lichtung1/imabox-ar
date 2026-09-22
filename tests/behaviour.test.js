import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import fs from 'node:fs';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {SequencePlayer,CharacterRig,posedBounds,resolveSequence} from '../js/animation.js';
import {approachProgress,stopBeforeViewer} from '../js/movement.js';
import {platformRoute,inAppBrowser,timeoutSignal,available} from '../js/platform.js';
// Read the shipped configuration rather than restating it. The previous version
// of this test passed sequence:null for char1, so when char1.glb gained a second
// clip the test kept testing a model the site never loads.
const characters=(()=>{
 const window={};
 new Function('window',fs.readFileSync(new URL('../characters.js',import.meta.url),'utf8'))(window);
 return window;
})();
const config=id=>({...characters.IMABOX_DEFAULTS,
 ...characters.IMABOX_CHARACTERS.find(c=>c.id===id)});
const clip=(name,target,values,duration=2)=>new THREE.AnimationClip(name,duration,[new THREE.NumberKeyframeTrack(target,[0,duration],values)]);
test('the ending finishes and holds after forward travel stops',()=>{
 const model=new THREE.Group();const player=new SequencePlayer(model,[clip('full','.position[y]',[0,9],9)],null);
 player.update(3);assert.equal(approachProgress(player.time,{start:1,end:3}),1);assert.equal(player.complete,false);
 player.update(6);assert.equal(player.complete,true);assert.equal(model.position.y,9);
 player.update(20);assert.equal(model.position.y,9);player.reset();assert.equal(model.position.y,0);
});
test('all disjoint object clips run together through the longest clip',()=>{
 const model=new THREE.Group();const player=new SequencePlayer(model,[clip('body','.position[y]',[0,2]),clip('wing','.rotation[z]',[0,4],4)],null);
 player.update(3);assert.equal(model.position.y,2);assert.equal(player.complete,false);player.update(1);assert.equal(model.rotation.z,4);
});
test('overlapping alternatives require explicit ordering and no clips may be silently omitted',()=>{
 const clips=[clip('run','.position[x]',[0,2]),clip('end','.position[x]',[2,5],3)];
 assert.throws(()=>resolveSequence(clips,null),/overlap/);
 assert.throws(()=>resolveSequence(clips,[{clips:['run']}]),/omits/);
 const model=new THREE.Group();const player=new SequencePlayer(model,clips,[{clips:['run']},{clips:['end']}]);
 player.update(5);assert.equal(player.duration,5);assert.equal(model.position.x,5);assert.equal(player.complete,true);
 player.reset();player.update(2.5);assert.ok(Math.abs(model.position.x-2.5)<1e-6);
});
test('a long frame cannot cross the stopping circle and latch can stop at boundary',()=>{
 const result=stopBeforeViewer({x:0,z:-5},{x:0,z:5},{x:0,z:0},2);
 assert.equal(result.stopped,true);assert.ok(Math.abs(result.fraction-.3)<1e-9);
 assert.equal(stopBeforeViewer({x:0,z:-2},{x:0,z:-1},{x:0,z:0},2).fraction,0);
});
test('routes Apple independently from GLB and catches iPad desktop user agents',()=>{
 assert.equal(platformRoute('iPhone','iPhone',1,true,false),'apple');
 assert.equal(platformRoute('Macintosh','MacIntel',5,true,false),'apple');
 assert.equal(platformRoute('Android Firefox/145','Linux',1,false,false),'android-browser');
 assert.equal(platformRoute('Android Chrome/145','Linux',1,false,true),'webxr');
 assert.equal(platformRoute('Desktop','Linux',0,false,false),'desktop');
});
test('real skinned model is grounded/scaled and root travel compensated, including replay/final pose',async()=>{
 globalThis.self=globalThis;
 const loader=new GLTFLoader().register(parser=>{parser.loadTexture=async()=>new THREE.Texture();return {name:'test-textures'};});
 // Look the settings up by file, not by id: char1.glb is not character 01.
 const settings=characters.IMABOX_CHARACTERS.find(c=>c.glb==='char1.glb');
 assert.ok(settings,'no character loads char1.glb');
 const b=fs.readFileSync(new URL('../char1.glb',import.meta.url));const gltf=await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'');
 const rig=new CharacterRig(gltf,{...config(settings.id),height:1,facingDegrees:0,groundOffset:0});
 const initial=posedBounds(rig.model);assert.ok(Math.abs(initial.min.y)<1e-6);assert.ok(Math.abs(initial.max.y-1)<1e-6);
 const anchor=rig.tracker.getWorldPosition(new THREE.Vector3());
 rig.actor.position.set(1,.7,-5);rig.actor.rotation.y=.8;rig.seek(3.5);
 const expected=rig.actor.localToWorld(anchor.clone()),actual=rig.tracker.getWorldPosition(new THREE.Vector3());
 assert.ok(Math.hypot(actual.x-expected.x,actual.z-expected.z)<1e-5);
 rig.seek(rig.player.duration);const final=posedBounds(rig.model).clone();rig.update(20);
 assert.ok(final.min.distanceTo(posedBounds(rig.model).min)<1e-6);
 rig.actor.position.set(0,0,0);rig.actor.rotation.y=0;rig.reset();assert.ok(Math.abs(posedBounds(rig.model).min.y)<1e-6);
});
test('every shipped character config actually resolves against its own GLB',async()=>{
 globalThis.self=globalThis;
 const loader=new GLTFLoader().register(parser=>{parser.loadTexture=async()=>new THREE.Texture();return {name:'test-textures'};});
 for(const c of characters.IMABOX_CHARACTERS){
  const b=fs.readFileSync(new URL('../'+c.glb,import.meta.url));
  const gltf=await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'');
  const settings={...characters.IMABOX_DEFAULTS,...c};
  // This is the check that was missing: a model whose clips drive the same
  // tracks needs an explicit sequence or the whole experience fails to mount.
  assert.doesNotThrow(()=>resolveSequence(gltf.animations,settings.sequence,settings.ignore||[]),`${c.id} (${c.glb})`);
  const rig=new CharacterRig(gltf,settings);
  assert.ok(Math.abs(posedBounds(rig.model).min.y)<1e-6,`${c.id} starts on the floor`);
  assert.ok(Math.abs(posedBounds(rig.model).max.y-settings.height)<1e-6,`${c.id} is the configured height`);
 }
});
test('a stale expectedSHA256 would silently discard the sequence, so it must match the file',async()=>{
 const {createHash}=await import('node:crypto');
 for(const c of characters.IMABOX_CHARACTERS.filter(c=>c.expectedSHA256)){
  const digest=createHash('sha256').update(fs.readFileSync(new URL('../'+c.glb,import.meta.url))).digest('hex');
  assert.equal(digest,c.expectedSHA256,`${c.id}: ${c.glb} does not match its configured hash`);
 }
});
test('asset checks separate "definitely missing" from "could not tell"',async()=>{
 const original=globalThis.fetch;
 const reply=(status,type)=>async()=>({ok:status<400,status,headers:{get:()=>type}});
 globalThis.fetch=reply(200,'model/vnd.usdz+zip');assert.equal(await available('x'),'ok');
 globalThis.fetch=reply(404,'text/html');assert.equal(await available('x'),'missing');
 globalThis.fetch=reply(200,'text/html; charset=utf-8');assert.equal(await available('x'),'missing');
 globalThis.fetch=reply(503,'text/plain');assert.equal(await available('x'),'unknown');
 globalThis.fetch=async()=>{throw new TypeError('network');};assert.equal(await available('x'),'unknown');
 globalThis.fetch=original;
});
test('the request timeout does not depend on AbortSignal.timeout, absent before Safari 16',()=>{
 const original=AbortSignal.timeout;
 try{
  delete AbortSignal.timeout;
  const signal=timeoutSignal(50);
  assert.ok(signal instanceof AbortSignal);assert.equal(signal.aborted,false);
 } finally {AbortSignal.timeout=original;}
 assert.ok(timeoutSignal(50) instanceof AbortSignal);
});
test('social in-app browsers are routed to Safari instead of a Quick Look link that does nothing',()=>{
 const ios='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15';
 assert.equal(platformRoute(ios+' Instagram 300.0.0',' iPhone',1,true,false),'apple-inapp');
 assert.equal(platformRoute(ios+' [FBAN/FBIOS]','iPhone',1,true,false),'apple-inapp');
 assert.equal(platformRoute(ios+' Safari/604.1','iPhone',1,true,false),'apple');
 assert.equal(inAppBrowser('Android Chrome/145'),false);
});
test('each page loads the model whose artwork matches its poster',async()=>{
 // The model files are not numbered like the posters, so this pairing is easy
 // to get wrong and impossible to notice from the code alone. Pin it.
 const expected={'01':'char4.glb','02':'char1.glb','03':'char3.glb','04':'char5.glb','05':'char2.glb'};
 for(const c of characters.IMABOX_CHARACTERS){
  assert.equal(c.glb,expected[c.id],`character ${c.id} should load ${expected[c.id]}`);
  assert.equal(c.usdz,expected[c.id].replace('.glb','.usdz'),`${c.id}: usdz must match its glb`);
  assert.equal(c.image,`assets/imabox--${c.id}.png`,`${c.id}: poster must match its id`);
 }
});
test('a duplicate clip can be ignored, but only when named',()=>{
 const clips=[clip('full','.position[y]',[0,9],9),clip('tail','.position[y]',[6,9],3)];
 // Both drive the same track, so nothing can be inferred.
 assert.throws(()=>resolveSequence(clips,null),/overlap/);
 // Leaving one out silently is still refused...
 assert.throws(()=>resolveSequence(clips,[{clips:['full']}]),/omits/);
 // ...but naming it as a duplicate is allowed, and it does not play.
 const only=resolveSequence(clips,[{clips:['full']}],['tail']);
 assert.equal(only.length,1);assert.equal(only[0].duration,9);
 // Typos and contradictions are caught rather than silently dropping animation.
 assert.throws(()=>resolveSequence(clips,[{clips:['full']}],['nope']),/not uniquely found/);
 assert.throws(()=>resolveSequence(clips,[{clips:['full','tail']}],['tail']),/both ignored and sequenced/);
});
test('the launch plays once, not twice',async()=>{
 globalThis.self=globalThis;
 const loader=new GLTFLoader().register(parser=>{parser.loadTexture=async()=>new THREE.Texture();return {name:'test-textures'};});
 for(const c of characters.IMABOX_CHARACTERS){
  const b=fs.readFileSync(new URL('../'+c.glb,import.meta.url));
  const gltf=await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'');
  const settings={...characters.IMABOX_DEFAULTS,...c};
  const rig=new CharacterRig(gltf,settings);
  // Sample how high the character gets across the whole sequence. A take-off
  // that is played twice shows up as a second climb after a return to ground.
  const N=90, heights=[];
  for(let i=0;i<N;i++){ rig.seek(rig.player.duration*i/(N-1)); heights.push(posedBounds(rig.model).max.y); }
  const floorish=heights[0]*1.6;
  let climbs=0, up=false;
  for(const h of heights){ if(!up&&h>floorish){climbs++;up=true;} else if(up&&h<floorish){up=false;} }
  assert.ok(climbs<=1,`${c.id} (${c.glb}) leaves the ground ${climbs} times; the launch is playing more than once`);
 }
});
test('measured opening approaches move once and finish at the stopping distance',()=>{
 for(const c of characters.IMABOX_CHARACTERS){
  const a=c.approach,p=a.keyframes;
  assert.equal(p[0][0],0);assert.equal(p[0][1],0);assert.equal(p.at(-1)[1],1);
  for(let i=1;i<p.length;i++){assert.ok(p[i][0]>p[i-1][0]);assert.ok(p[i][1]>=p[i-1][1]);}
  assert.ok(approachProgress(.5,a)>0,`${c.id} includes opening motion`);
  assert.equal(approachProgress(a.end+20,a),1);
  const settings=config(c.id),from={x:0,z:-settings.startDistance},viewer={x:0,z:0};
  let position={...from},stopped=false;
  for(let t=0;t<a.end+.1;t+=1/60){
   const candidate={x:0,z:-settings.startDistance+(settings.startDistance-settings.stopDistance)*approachProgress(t,a)};
   if(!stopped){const r=stopBeforeViewer(position,candidate,viewer,settings.stopDistance);position.z+=(candidate.z-position.z)*r.fraction;stopped=r.stopped;}
   assert.ok(position.z<=-settings.stopDistance+1e-8);
  }
  assert.ok(Math.abs(position.z+settings.stopDistance)<1e-6);
 }
});
test('every USDZ matches its recorded hash and all public routes exist',async()=>{
 const {createHash}=await import('node:crypto');
 for(const c of characters.IMABOX_CHARACTERS){
  const digest=createHash('sha256').update(fs.readFileSync(new URL('../'+c.usdz,import.meta.url))).digest('hex');
  assert.equal(digest,c.expectedUSDZSHA256);
  const html=fs.readFileSync(new URL(`../characters/${c.id}/index.html`,import.meta.url),'utf8');
  assert.ok(html.includes(`data-character="${c.id}"`));
  assert.ok(html.includes(characters.IMABOX_BUILD));
  assert.ok(fs.existsSync(new URL('../'+c.image,import.meta.url)));
 }
 assert.ok(fs.existsSync(new URL('../index.html',import.meta.url)));
});
test('new exports contain exactly one complete scene timeline',async()=>{
 globalThis.self=globalThis;
 const loader=new GLTFLoader().register(p=>{p.loadTexture=async()=>new THREE.Texture();return {name:'test-textures'};});
 for(const c of characters.IMABOX_CHARACTERS){
  const b=fs.readFileSync(new URL('../'+c.glb,import.meta.url));
  const g=await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'');
  assert.deepEqual(g.animations.map(a=>a.name),['Scene']);
  assert.ok(Math.abs(g.animations[0].duration-c.animationDuration)<1e-5);
  const rig=new CharacterRig(g,config(c.id));rig.seek(rig.player.duration);
  const before=posedBounds(rig.model).clone();rig.update(100);
  assert.ok(before.min.distanceTo(posedBounds(rig.model).min)<1e-6);
 }
});
test('char5 aura is hidden initially, deforms during its visible interval, and disappears before the ending',async()=>{
 globalThis.self=globalThis;
 const loader=new GLTFLoader().register(p=>{p.loadTexture=async()=>new THREE.Texture();return {name:'test-textures'};});
 const b=fs.readFileSync(new URL('../char5.glb',import.meta.url));const g=await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'');
 const rig=new CharacterRig(g,config('04')),aura=rig.model.getObjectByName('Aura_Baked');
 assert.ok(aura?.isMesh);assert.ok(aura.userData.excludeFromGrounding);assert.equal(aura.scale.length(),0);
 rig.seek(75/24);assert.ok(aura.scale.length()>0);const first=aura.getVertexPosition(100,new THREE.Vector3());
 rig.seek(100/24);const second=aura.getVertexPosition(100,new THREE.Vector3());assert.ok(first.distanceTo(second)>1e-5);
 rig.seek(233/24);assert.equal(aura.scale.length(),0);
 assert.ok(rig.player.duration>233/24);
});
