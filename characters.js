// Change this label and assetRevision when replacing code or models.
window.IMABOX_BUILD = 'v11-20260921.1';
window.IMABOX_DEFAULTS = {
  startDistance: 5, // Provisional metres; a level floor is assumed out to this point.
  stopDistance: 2,
  height: 1, // Character height in metres at the initial animated pose.
  facingDegrees: 0,
  groundOffset: 0, // Metres. Only change after checking the actual export on a device.
  // null: show full animation in place until a running interval is reviewed.
  approach: null,
  // null: one clip, or simultaneous clips with disjoint tracks, inferred safely.
  // For consecutive clips use [{clips:['Run']}, {clips:['Ending']}].
  sequence: null,
  // Clips that duplicate something already playing. Listing one here is the
  // only way to leave a clip out; a silent omission is still an error.
  ignore: null,
  motionNode: null // Auto: Frame, Root, or scene root. Set exact name for other rigs.
};
// The model files are NOT numbered the same way as the posters. charN.glb does
// not hold the character in imabox--0N.png; the torso textures baked into each
// file say so plainly. The poster numbering is the real one -- the accent
// colours below were written against it -- so each entry points at whichever
// model actually carries that character's artwork:
//
//   01 green      -> char4     02 orange     -> char1     03 blue -> char3
//   04 pink       -> char5     05 red "21"   -> char2
//
// Per-model settings travel with the model, not with the id.
//
// char1 and char5 pair ArmatureAction with a Fly_Away clip that drives the same
// bones, so nothing can be inferred and an explicit sequence is required or
// resolveSequence throws 'Animation clips overlap' and the experience never
// mounts. Fly_Away is not a second half -- it is the tail of ArmatureAction
// exported again on its own -- so it is ignored rather than appended.
window.IMABOX_CHARACTERS = [
  { id:'01', name:'Imabox 01', color:'#228442', image:'assets/imabox--01.png',
    glb:'char4.glb', usdz:'char4.usdz', assetRevision:'v11-20260921.1',
    // Walks in over the first 1.08 s. startDistance is stopDistance plus the
    // 1.24 m the feet actually cover, so the approach does not outrun the steps.
    approach:{start:0,end:1.08}, startDistance:3.24 },
  { id:'02', name:'Imabox 02', color:'#fa601c', image:'assets/imabox--02.png',
    glb:'char1.glb', usdz:'char1.usdz', assetRevision:'v11-20260921.1',
    // SHA of the char1.glb actually in this repository. The previous value was
    // for an older export, so every load discarded the settings below and then
    // failed on the un-sequenced clips.
    expectedSHA256:'14cbaf3fe2eb9e9ba54ae622bcc96c1aea1a221fe3c7f537c7af107b2d48e031',
    motionNode:'Frame',
    // Fly_Away is the last seconds of ArmatureAction exported again on its own.
    // Playing both launched the character, put it back on the floor and
    // launched it a second time.
    sequence:[{clips:['ArmatureAction']}], ignore:['Fly_Away'],
    // Measured on the char1.glb in this repository, not inherited from the
    // older export: it advances 2.60 m between 1.65 s and 3.87 s.
    approach:{start:1.65,end:3.87}, startDistance:4.60 },
  // 03 and 05 have no walk in their animation -- the root never advances, they
  // perform where they are put. There is nothing to drive an approach with.
  { id:'03', name:'Imabox 03', color:'#4297ce', image:'assets/imabox--03.png',
    glb:'char3.glb', usdz:'char3.usdz', assetRevision:'v11-20260921.1' },
  { id:'04', name:'Imabox 04', color:'#ef7dac', image:'assets/imabox--04.png',
    glb:'char5.glb', usdz:'char5.usdz', assetRevision:'v11-20260921.1',
    sequence:[{clips:['ArmatureAction','displacecontrolerAction','auraAction','aura visibility controlerAction']}],
    ignore:['Fly_Away'],
    approach:{start:0,end:1.08}, startDistance:3.24 },
  { id:'05', name:'Imabox 05', color:'#f31522', image:'assets/imabox--05.png',
    glb:'char2.glb', usdz:'char2.usdz', assetRevision:'v11-20260921.1' }
];
