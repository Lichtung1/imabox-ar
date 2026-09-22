import * as THREE from 'three';

// Validate explicitly grouped clips and deliberate omissions.
export function resolveSequence(clips, config, ignore) {
  if (!clips.length) return [];
  const skip = new Set();
  // Not a default parameter: the defaults in characters.js spell "nothing to
  // ignore" as null, and a default only fills in for undefined.
  for (const name of ignore || []) {
    const matches = clips.filter((c) => c.name === name);
    if (matches.length !== 1) throw Error(`Ignored animation clip not uniquely found: ${name}`);
    skip.add(name);
  }
  const playable = clips.filter((c) => !skip.has(c.name));
  let groups = config;
  if (!groups) {
    const occupied = new Set();
    for (const clip of playable)
      for (const track of clip.tracks) {
        if (occupied.has(track.name))
          throw Error('Animation clips overlap. Set the intended sequence in characters.js.');
        occupied.add(track.name);
      }
    groups = [{ clips: playable.map((c) => c.name) }];
  }
  const seen = new Set();
  const sequence = groups.map((group) => {
    const tracks = new Set();
    const selected = group.clips.map((name) => {
      if (skip.has(name)) throw Error(`Clip is both ignored and sequenced: ${name}`);
      const matches = playable.filter((c) => c.name === name);
      if (matches.length !== 1) throw Error(`Animation clip not uniquely found: ${name}`);
      const clip = matches[0];
      if (seen.has(name)) throw Error(`Repeated clip: ${name}`);
      seen.add(name);
      for (const t of clip.tracks) {
        if (tracks.has(t.name)) throw Error(`Conflicting simultaneous animation: ${t.name}`);
        tracks.add(t.name);
      }
      return clip;
    });
    if (!selected.length) throw Error('Empty animation group.');
    return { clips: selected, duration: Math.max(...selected.map((c) => c.duration)) };
  });
  if (seen.size !== playable.length)
    throw Error(
      'Sequence omits animation clips. Review every clip before publishing, and list deliberate omissions in `ignore`.',
    );
  return sequence;
}
function snapshot(model) {
  const values = [];
  model.traverse((n) =>
    values.push([
      n,
      n.position.clone(),
      n.quaternion.clone(),
      n.scale.clone(),
      n.morphTargetInfluences?.slice(),
    ]),
  );
  return () => {
    for (const [n, p, q, s, m] of values) {
      n.position.copy(p);
      n.quaternion.copy(q);
      n.scale.copy(s);
      if (m) n.morphTargetInfluences.splice(0, m.length, ...m);
    }
  };
}
export class SequencePlayer {
  constructor(model, clips, config, ignore) {
    this.model = model;
    this.groups = resolveSequence(clips, config, ignore);
    this.duration = this.groups.reduce((sum, g) => sum + g.duration, 0);
    this.mixer = new THREE.AnimationMixer(model);
    this.restore = snapshot(model);
    this.reset();
  }
  enter(index) {
    // Retain the outgoing final pose for properties not keyed by the next group.
    const retain = snapshot(this.model);
    this.mixer.stopAllAction();
    retain();
    this.index = index;
    for (const clip of this.groups[index]?.clips || []) {
      const action = this.mixer.clipAction(clip);
      action.reset();
      action.setLoop(THREE.LoopOnce, 1);
      action.clampWhenFinished = true;
      action.play();
    }
    this.mixer.update(0);
  }
  reset() {
    this.mixer.stopAllAction();
    this.restore();
    this.time = 0;
    this.localTime = 0;
    this.enter(0);
  }
  update(dt) {
    let remaining = Math.max(0, Math.min(dt, this.duration - this.time));
    while (remaining > 1e-9 && this.groups[this.index]) {
      const step = Math.min(remaining, this.groups[this.index].duration - this.localTime);
      this.mixer.update(step);
      this.time += step;
      this.localTime += step;
      remaining -= step;
      if (
        this.localTime >= this.groups[this.index].duration - 1e-8 &&
        this.index + 1 < this.groups.length
      ) {
        this.enter(this.index + 1);
        this.localTime = 0;
      } else if (step === 0) break;
    }
  }
  seek(time) {
    this.reset();
    this.update(Math.min(time, this.duration));
  }
  get complete() {
    return this.time >= this.duration - 1e-7;
  }
}

export function posedBounds(model) {
  let root = model;
  while (root.parent) root = root.parent;
  root.updateMatrixWorld(true);
  model.traverse((n) => {
    if (n.isSkinnedMesh) n.skeleton.update();
  });
  const bounds = new THREE.Box3();
  model.traverse((n) => {
    if (n.isMesh && !n.userData.excludeFromGrounding) bounds.expandByObject(n, true);
  });
  return bounds;
}
export class CharacterRig {
  constructor(gltf, config) {
    this.config = config;
    this.model = gltf.scene;
    this.model.traverse((n) => {
      if ((config.effectNodes || []).includes(n.name)) n.userData.excludeFromGrounding = true;
    });
    this.actor = new THREE.Group();
    this.lift = new THREE.Group();
    this.heading = new THREE.Group();
    this.size = new THREE.Group();
    this.compensation = new THREE.Group();
    this.actor.add(this.lift);
    this.lift.add(this.heading);
    this.heading.add(this.size);
    this.size.add(this.compensation);
    this.compensation.add(this.model);
    this.player = new SequencePlayer(this.model, gltf.animations, config.sequence, config.ignore);
    const bounds = posedBounds(this.model),
      centre = bounds.getCenter(new THREE.Vector3());
    const height = bounds.max.y - bounds.min.y;
    if (!(height > 0 && Number.isFinite(height))) throw Error('Model has no visible height.');
    this.baseOffset = new THREE.Vector3(-centre.x, -bounds.min.y, -centre.z);
    this.tracker = config.motionNode
      ? this.model.getObjectByName(config.motionNode)
      : this.model.getObjectByName('Frame') || this.model.getObjectByName('Root') || this.model;
    if (!this.tracker) throw Error(`Motion node not found: ${config.motionNode}`);
    this.origin = this.trackerPoint();
    this.compensation.position.copy(this.baseOffset);
    this.size.scale.setScalar(config.height / height);
    this.heading.rotation.y = THREE.MathUtils.degToRad(config.facingDegrees);
    // Do not cache rest-pose bounds for a skinned export. Ground its evaluated pose.
    this.lift.position.y = -posedBounds(this.model).min.y + config.groundOffset;
    this.baseLift = this.lift.position.y;
    this.initialGround = posedBounds(this.model).min.y;
  }
  trackerPoint() {
    // Parent space includes scene-root animation as well as animated armatures.
    this.actor.updateMatrixWorld(true);
    return this.compensation.worldToLocal(this.tracker.getWorldPosition(new THREE.Vector3()));
  }
  compensate() {
    const delta = this.trackerPoint().sub(this.origin);
    this.compensation.position.copy(this.baseOffset);
    this.compensation.position.x -= delta.x;
    this.compensation.position.z -= delta.z;
    // Keep authored bounce/jumps, but prevent deformed feet sinking below the floor.
    // Re-evaluate actual skinned vertices, not the cached bind-pose bounding box.
    this.lift.position.y = this.baseLift;
    if (this.config.preventFloorPenetration !== false) {
      const floor = this.actor.position.y + this.config.groundOffset;
      const minY = posedBounds(this.model).min.y;
      this.lift.position.y += Math.max(0, floor - minY);
    }
  }
  reset() {
    this.player.reset();
    this.compensate();
  }
  update(dt) {
    this.player.update(dt);
    this.compensate();
  }
  seek(t) {
    this.player.seek(t);
    this.compensate();
  }
}
