// Which AR path this device can take, and whether an asset is really there.

// Safari only shipped AbortSignal.timeout in 16.0. On an older iPhone the bare
// call throws, and because the fetch below is wrapped in a try/catch that
// returns "no", every asset check silently failed and the iPhone was told its
// character was unavailable. Same story for experience.js.
export function timeoutSignal(ms) {
  if (typeof AbortSignal !== 'undefined' && AbortSignal.timeout) {
    try { return AbortSignal.timeout(ms); } catch {}
  }
  if (typeof AbortController === 'undefined') return undefined;
  const controller = new AbortController();
  setTimeout(() => controller.abort(), ms);
  return controller.signal;
}

// Quick Look does not run inside most social-app browsers. The link is there
// and rel="ar" may even report as supported, but the tap does nothing, which
// is the other common way an iPhone visitor sees "nothing happens".
export function inAppBrowser(ua) {
  return /FBAN|FBAV|FB_IAB|Instagram|Line\/|Twitter|TikTok|Snapchat|LinkedInApp|Pinterest|WhatsApp|MicroMessenger/i.test(ua);
}

export function platformRoute(ua, platform, touches, quickLook, xr) {
  if (/iPhone|iPad|iPod/i.test(ua) || (platform === 'MacIntel' && touches > 1)) {
    if (inAppBrowser(ua)) return 'apple-inapp';
    return quickLook ? 'apple' : 'apple-browser';
  }
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

// Three states, not two. "unknown" means the check itself failed -- offline for
// a moment, a proxy that refuses HEAD, a timeout on a slow connection. Treating
// that as "missing" is what hid the AR button on iPhones whose file was fine.
export async function available(url) {
  try {
    const r = await fetch(url, {method: 'HEAD', cache: 'no-cache', signal: timeoutSignal(12000)});
    if (r.status === 404 || r.status === 410) return 'missing';
    if (!r.ok) return 'unknown';
    if (/text\/html/i.test(r.headers.get('content-type') || '')) return 'missing';
    return 'ok';
  } catch {
    return 'unknown';
  }
}
