export function platformRoute(ua, platform, touches, quickLook, xr) {
  if (/iPhone|iPad|iPod/i.test(ua) || (platform === 'MacIntel' && touches > 1))
    return quickLook ? 'apple' : 'apple-browser';
  if (xr) return 'webxr';
  if (/Android/i.test(ua))
    return /Chrome\//.test(ua) && !/(EdgA|OPR|SamsungBrowser)\//.test(ua) ? 'android-unavailable' : 'android-browser';
  return 'desktop';
}
export async function detectPlatform() {
  let xr = false, quickLook = false;
  try { xr = !!navigator.xr && await navigator.xr.isSessionSupported('immersive-ar'); } catch {}
  try { quickLook = document.createElement('a').relList.supports('ar'); } catch {}
  return platformRoute(navigator.userAgent, navigator.platform, navigator.maxTouchPoints || 0, quickLook, xr);
}
export async function available(url) {
  try {
    const r = await fetch(url, {method:'HEAD', cache:'no-cache', signal:AbortSignal.timeout(12000)});
    return r.ok && !/text\/html/i.test(r.headers.get('content-type') || '');
  } catch { return false; }
}
