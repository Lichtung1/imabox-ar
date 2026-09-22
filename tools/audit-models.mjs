// Run: npm install && npm run audit. Does not modify models.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { CharacterRig, posedBounds } from '../js/animation.js';
globalThis.self = globalThis;
const root = path.resolve(import.meta.dirname, '..'),
  scope = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(root, 'characters.js'), 'utf8'), scope);
const result = {
  build: scope.window.IMABOX_BUILD,
  note: 'Numeric animation/geometry inspection. Textures skipped only by this audit. No phone hardware tested.',
  characters: [],
};
for (const character of scope.window.IMABOX_CHARACTERS) {
  const record = {
    id: character.id,
    glb: character.glb,
    usdz: character.usdz,
    glbPresent: fs.existsSync(path.join(root, character.glb)),
    usdzPresent: fs.existsSync(path.join(root, character.usdz)),
  };
  result.characters.push(record);
  if (!record.glbPresent) continue;
  const buffer = fs.readFileSync(path.join(root, character.glb));
  record.bytes = buffer.length;
  record.sha256 = crypto.createHash('sha256').update(buffer).digest('hex');
  const loader = new GLTFLoader().register((parser) => {
    parser.loadTexture = async () => new THREE.Texture();
    return { name: 'audit-skip-textures' };
  });
  try {
    const gltf = await loader.parseAsync(
      buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength),
      '',
    );
    record.clips = gltf.animations.map((c) => ({
      name: c.name,
      duration: c.duration,
      tracks: c.tracks.map((t) => t.name),
    }));
    let config = { ...scope.window.IMABOX_DEFAULTS, ...character };
    record.profileMatches = !config.expectedSHA256 || config.expectedSHA256 === record.sha256;
    if (!record.profileMatches) {
      config.sequence = null;
      config.motionNode = null;
      config.approach = null;
    }
    const rig = new CharacterRig(gltf, config);
    record.motionNode = rig.tracker.name;
    record.duration = rig.player.duration;
    const initial = posedBounds(rig.model);
    record.initialBounds = { min: initial.min.toArray(), max: initial.max.toArray() };
    record.samples = [];
    const anchor = rig.tracker.getWorldPosition(new THREE.Vector3());
    let horizontalError = 0,
      minGround = Infinity,
      maxGround = -Infinity;
    for (let i = 0; i <= Math.ceil(rig.player.duration * 30); i++) {
      const t = Math.min(i / 30, rig.player.duration);
      rig.seek(t);
      const p = rig.trackerPoint(),
        world = rig.tracker.getWorldPosition(new THREE.Vector3()),
        bounds = posedBounds(rig.model);
      horizontalError = Math.max(
        horizontalError,
        Math.hypot(world.x - anchor.x, world.z - anchor.z),
      );
      minGround = Math.min(minGround, bounds.min.y);
      maxGround = Math.max(maxGround, bounds.min.y);
      if (i % 15 === 0 || t === rig.player.duration)
        record.samples.push({
          time: t,
          motionNode: p.toArray(),
          bottom: bounds.min.y,
          top: bounds.max.y,
        });
    }
    record.maxHorizontalCompensationError = horizontalError;
    record.lowestPointRange = [minGround, maxGround];
    record.finalBounds = {
      min: posedBounds(rig.model).min.toArray(),
      max: posedBounds(rig.model).max.toArray(),
    };
    const finalTracks = {};
    rig.model.traverse((n) => {
      if (n.isBone || n.name === 'Armature')
        finalTracks[n.name] = {
          position: n.position.toArray(),
          quaternion: n.quaternion.toArray(),
          scale: n.scale.toArray(),
        };
    });
    record.finalPose = finalTracks;
    rig.update(10);
    record.finalPoseHeld =
      posedBounds(rig.model).min.distanceTo(new THREE.Vector3().fromArray(record.finalBounds.min)) <
      1e-7;
  } catch (error) {
    record.error = error.message;
  }
}
console.log(JSON.stringify(result, null, 2));
