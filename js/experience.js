import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {CharacterRig,posedBounds} from './animation.js?v=v7-20260921.1';
import {approachProgress,stopBeforeViewer} from './movement.js?v=v7-20260921.1';

export async function mountExperience({config,url,route,art,enter,preview,setStatus}) {
  config={...config};
  const response=await fetch(url,{signal:AbortSignal.timeout(45000)});
  if(!response.ok)throw Error(`Model request failed (${response.status}).`);
  const bytes=await response.arrayBuffer();
  if(config.expectedSHA256) {
    const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
    if(digest!==config.expectedSHA256) {
      // A replacement export must not inherit old timing or clip-name assumptions.
      console.warn('New export detected: review animation timing, root node and sequence in characters.js.');
      config.approach=null;config.sequence=null;config.motionNode=null;
    }
  }
  const gltf=await new GLTFLoader().parseAsync(bytes,new URL('.',url).href);
  const rig=new CharacterRig(gltf,config);
  if(config.approach && !(config.approach.start>=0 && config.approach.end>config.approach.start && config.approach.end<=rig.player.duration+.001))throw Error('The configured running interval is outside this animation.');
  if(!(config.startDistance>config.stopDistance && config.stopDistance>0 && config.height>0))throw Error('Invalid character placement settings.');
  const scene=new THREE.Scene();scene.add(rig.actor);
  scene.add(new THREE.HemisphereLight(0xffffff,0x8a8a8a,2.4));
  const sun=new THREE.DirectionalLight(0xffffff,2.6);sun.position.set(3,5,4);scene.add(sun);
  const camera=new THREE.PerspectiveCamera(42,1,.01,100);
  camera.position.set(0,config.height*.65,config.height*2.5);
  const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.xr.enabled=true;renderer.xr.setReferenceSpaceType('local');
  renderer.domElement.setAttribute('aria-label',`${config.name} animated 3D preview`);
  art.replaceChildren(renderer.domElement);
  const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,config.height*.45,0);controls.enablePan=false;controls.minDistance=config.height;controls.maxDistance=config.height*5;controls.update();controls.saveState();
  const marker=new THREE.Mesh(new THREE.RingGeometry(.14,.19,40).rotateX(-Math.PI/2),new THREE.MeshBasicMaterial({color:0xfa601c,side:THREE.DoubleSide}));
  marker.visible=false;scene.add(marker);
  const overlay=document.createElement('div');overlay.id='xr-ui';overlay.hidden=true;
  overlay.innerHTML=`<div class="xr-panel"><p id="xr-status" role="status"></p><p class="xr-build">IMABOX · ${window.IMABOX_BUILD}</p></div><div class="xr-panel xr-actions"><button id="place" disabled>PLACE & PLAY</button><button id="again" hidden>PLAY AGAIN</button><button id="rescan" hidden>PLACE AGAIN</button><button id="exit">EXIT AR</button></div>`;
  document.body.append(overlay);
  const $=id=>overlay.querySelector('#'+id),message=text=>$('xr-status').textContent=text;
  overlay.addEventListener('beforexrselect',event=>event.preventDefault());
  let session=null,hitSource=null,state='preview',playing=false,lastTime=null,validMarkerTime=0,travelStopped=false,disposed=false;
  const spawn=new THREE.Vector3(),start=new THREE.Vector3(),end=new THREE.Vector3(),viewer=new THREE.Vector3(),forward=new THREE.Vector3(),candidate=new THREE.Vector3();
  const hitMatrix=new THREE.Matrix4(),hitPoint=new THREE.Vector3(),orientation=new THREE.Quaternion();
  function sizeCanvas(){if(disposed)return;const w=session?innerWidth:art.clientWidth,h=session?innerHeight:art.clientHeight;camera.aspect=w/Math.max(1,h);camera.updateProjectionMatrix();renderer.setSize(w,Math.max(1,h),false);}
  const resizeObserver=new ResizeObserver(sizeCanvas);resizeObserver.observe(art);addEventListener('resize',sizeCanvas);sizeCanvas();
  function play(){rig.reset();playing=true;travelStopped=false;if(session){rig.actor.position.copy(start);state='playing';marker.visible=false;$('again').hidden=true;message('Watch your character.');}else {preview.textContent='RESTART ANIMATION';setStatus('Playing the full animation.');}}
  preview.hidden=rig.player.duration===0;preview.disabled=false;preview.textContent='PLAY ANIMATION';preview.onclick=play;
  function scan(){state='scanning';playing=false;rig.actor.visible=false;marker.visible=false;validMarkerTime=0;$('place').hidden=false;$('place').disabled=true;$('again').hidden=true;$('rescan').hidden=true;message('Point at a clear, level floor and move your phone slowly.');}
  function restore(){
    hitSource?.cancel();hitSource=null;session=null;state='preview';playing=false;lastTime=null;
    document.body.classList.remove('in-ar');overlay.hidden=true;marker.visible=false;
    rig.actor.visible=true;rig.actor.position.set(0,0,0);rig.actor.rotation.set(0,0,0);rig.reset();
    controls.enabled=true;controls.reset();enter.disabled=false;preview.textContent='PLAY ANIMATION';sizeCanvas();
  }
  enter.hidden=route!=='webxr';enter.disabled=false;
  enter.onclick=async()=>{
    if(session)return;enter.disabled=true;
    try {
      // Request directly from the user gesture, before any loading or feature checks.
      const requested=await navigator.xr.requestSession('immersive-ar',{requiredFeatures:['hit-test','dom-overlay'],domOverlay:{root:overlay}});
      session=requested;requested.addEventListener('end',restore,{once:true});
      overlay.hidden=false;document.body.classList.add('in-ar');
      await renderer.xr.setSession(requested);
      if(session!==requested)return;
      const space=await requested.requestReferenceSpace('viewer');
      const source=await requested.requestHitTestSource({space});
      if(session!==requested){source.cancel();return;}
      hitSource=source;controls.enabled=false;sizeCanvas();scan();
    } catch(error) {
      if(session){try{await session.end();}catch{restore();}}else restore();
      setStatus('Could not start AR. Use Chrome on a supported Android phone and allow camera access. '+error.message);
    }
  };
  $('exit').onclick=()=>session?.end();$('rescan').onclick=scan;$('again').onclick=play;
  $('place').onclick=()=>{
    if(state!=='scanning'||!marker.visible||performance.now()-validMarkerTime>250)return;
    // Copy the displayed position. Do not recalculate placement on tap.
    start.copy(spawn);forward.subVectors(start,viewer);forward.y=0;
    const distance=forward.length();if(distance<=config.stopDistance+.05){message('Point farther away to leave room for the approach.');return;}
    forward.normalize();end.copy(viewer).addScaledVector(forward,config.stopDistance);end.y=start.y;
    rig.actor.position.copy(start);rig.actor.rotation.y=Math.atan2(-forward.x,-forward.z);rig.actor.visible=true;
    $('place').hidden=true;$('rescan').hidden=false;play();
  };
  renderer.setAnimationLoop((time,frame)=>{
    const dt=lastTime===null?0:Math.max(0,Math.min((time-lastTime)/1000,.1));lastTime=time;
    let tracked=!session;
    if(session&&frame){
      const reference=renderer.xr.getReferenceSpace(),pose=frame.getViewerPose(reference);
      tracked=!!pose&&session.visibilityState==='visible';
      if(!tracked){marker.visible=false;validMarkerTime=0;$('place').disabled=true;message('Tracking paused. Move your phone slowly to find the room again.');}
      else {
        viewer.set(pose.transform.position.x,pose.transform.position.y,pose.transform.position.z);
        if(state==='scanning'&&hitSource){
          marker.visible=false;
          for(const hit of frame.getHitTestResults(hitSource)){
            const hp=hit.getPose(reference);if(!hp)continue;hitMatrix.fromArray(hp.transform.matrix);hitPoint.setFromMatrixPosition(hitMatrix);
            if(hitMatrix.elements[5]<.9||hitPoint.y>viewer.y-.25)continue;
            orientation.set(pose.transform.orientation.x,pose.transform.orientation.y,pose.transform.orientation.z,pose.transform.orientation.w);
            forward.set(0,0,-1).applyQuaternion(orientation);forward.y=0;if(forward.lengthSq()<.04)continue;
            spawn.copy(viewer).addScaledVector(forward.normalize(),config.startDistance);spawn.y=hitPoint.y;
            marker.position.copy(spawn);marker.position.y+=.005;marker.visible=true;validMarkerTime=performance.now();break;
          }
          $('place').disabled=!marker.visible;
          message(marker.visible?`The orange circle is the starting point, about ${config.startDistance} m away. Check that the floor is clear and level all the way there, then tap Place & Play.`:'Point at a clear, level floor and move your phone slowly.');
        }else if(playing)message(travelStopped?'Finishing the animation…':'Watch your character.');
      }
    }
    if(playing&&tracked&&!document.hidden){
      rig.update(dt);
      if(session&&!travelStopped&&config.approach){
        candidate.lerpVectors(start,end,approachProgress(rig.player.time,config.approach));
        const step=stopBeforeViewer(rig.actor.position,candidate,viewer,config.stopDistance);
        rig.actor.position.lerp(candidate,step.fraction);
        travelStopped=step.stopped||rig.player.time>=config.approach.end;
      }
      // Animation completion is independent of position and approach state.
      if(rig.player.complete){playing=false;preview.textContent='PLAY AGAIN';if(session){state='finished';$('again').hidden=false;message('Animation complete.');}else setStatus('Animation complete. Drag to look around, or play again.');}
    }
    renderer.render(scene,camera);
  });
  setStatus('Drag to look around, or play the animation.');
  if(new URLSearchParams(location.search).has('debug'))window.imaboxDebug={rig,scene,renderer,play,posedBounds,get state(){return state;}};
  addEventListener('pagehide',()=>{disposed=true;renderer.setAnimationLoop(null);resizeObserver.disconnect();removeEventListener('resize',sizeCanvas);controls.dispose();renderer.dispose();hitSource?.cancel();session?.end().catch(()=>{});},{once:true});
}
