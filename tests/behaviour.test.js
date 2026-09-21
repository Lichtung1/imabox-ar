import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import fs from 'node:fs';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {SequencePlayer,CharacterRig,posedBounds,resolveSequence} from '../js/animation.js';
import {approachProgress,stopBeforeViewer} from '../js/movement.js';
import {platformRoute} from '../js/platform.js';
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
 const b=fs.readFileSync(new URL('../char1.glb',import.meta.url));const gltf=await loader.parseAsync(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'');
 const rig=new CharacterRig(gltf,{height:1,facingDegrees:0,groundOffset:0,motionNode:'Frame',sequence:null});
 const initial=posedBounds(rig.model);assert.ok(Math.abs(initial.min.y)<1e-6);assert.ok(Math.abs(initial.max.y-1)<1e-6);
 const anchor=rig.tracker.getWorldPosition(new THREE.Vector3());
 rig.actor.position.set(1,.7,-5);rig.actor.rotation.y=.8;rig.seek(3.5);
 const expected=rig.actor.localToWorld(anchor.clone()),actual=rig.tracker.getWorldPosition(new THREE.Vector3());
 assert.ok(Math.hypot(actual.x-expected.x,actual.z-expected.z)<1e-5);
 rig.seek(rig.player.duration);const final=posedBounds(rig.model).clone();rig.update(20);
 assert.ok(final.min.distanceTo(posedBounds(rig.model).min)<1e-6);
 rig.actor.position.set(0,0,0);rig.actor.rotation.y=0;rig.reset();assert.ok(Math.abs(posedBounds(rig.model).min.y)<1e-6);
});
