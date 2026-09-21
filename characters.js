// Change this label and assetRevision when replacing code or models.
window.IMABOX_BUILD = 'v7-20260921.1';
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
  motionNode: null // Auto: Frame, Root, or scene root. Set exact name for other rigs.
};
window.IMABOX_CHARACTERS = [
  { id:'01', name:'Imabox 01', color:'#228442', image:'assets/imabox--01.png', glb:'char1.glb', usdz:'char1.usdz', assetRevision:'v7-20260921.1',
    // This profile is for the repository export, NOT the unprovided new char1.glb.
    expectedSHA256:'348b61ea4dd9e3c583ccc575b134f95ecbf681b62f6c52fed5d379bff626ea90', motionNode:'Frame',
    sequence:[{clips:['ArmatureAction']}], approach:{start:1.75,end:3.8333333333} },
  { id:'02', name:'Imabox 02', color:'#fa601c', image:'assets/imabox--02.png', glb:'char2.glb', usdz:'char2.usdz', assetRevision:'v7-20260921.1' },
  { id:'03', name:'Imabox 03', color:'#4297ce', image:'assets/imabox--03.png', glb:'char3.glb', usdz:'char3.usdz', assetRevision:'v7-20260921.1' },
  { id:'04', name:'Imabox 04', color:'#ef7dac', image:'assets/imabox--04.png', glb:'char4.glb', usdz:'char4.usdz', assetRevision:'v7-20260921.1' },
  { id:'05', name:'Imabox 05', color:'#f31522', image:'assets/imabox--05.png', glb:'char5.glb', usdz:'char5.usdz', assetRevision:'v7-20260921.1' }
];
