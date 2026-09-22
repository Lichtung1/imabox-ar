const siteRoot = new URL('./', document.currentScript.src);
const localUrl = (path) => new URL(path, siteRoot).href;
const build = window.IMABOX_BUILD;
const versioned = (path) => {
  const url = new URL(path, siteRoot);
  url.searchParams.set('v', build);
  return url.href;
};
const footer = document.createElement('footer');
footer.className = 'build';
footer.textContent = `IMABOX · ${build}`;
document.body.append(footer);
async function init() {
  const chars = window.IMABOX_CHARACTERS,
    detail = document.querySelector('[data-character]');
  if (!detail) {
    const query = new URLSearchParams(location.search),
      requested = query.get('character') || query.get('char');
    const linked = chars.find((c) => c.id === requested?.padStart(2, '0'));
    if (linked) {
      location.replace(versioned(`characters/${linked.id}/index.html`));
      return;
    }
    const gallery = document.querySelector('#gallery');
    gallery.replaceChildren();
    for (const c of chars) {
      const a = document.createElement('a');
      a.className = 'card';
      a.href = versioned(`characters/${c.id}/index.html`);
      a.style.setProperty('--accent', c.color);
      a.innerHTML = `
        <div class="art">
          <img src="${localUrl(c.image)}" alt="${c.name}" width="1080" height="1080" loading="lazy">
        </div>
        <div class="card-bottom">
          <span class="label">${c.name}</span>
          <span class="tap">TAP TO VIEW</span>
        </div>`;
      gallery.append(a);
    }
    return;
  }
  const index = chars.findIndex((c) => c.id === detail.dataset.character),
    c = chars[index];
  if (!c) throw Error('Unknown character');
  const previous = chars[(index + chars.length - 1) % chars.length],
    next = chars[(index + 1) % chars.length];
  const host = document.querySelector('#character');
  host.style.setProperty('--accent', c.color);
  host.innerHTML = `
    <div class="character-layout">
      <div class="character-art" id="art">
        <img id="poster" src="${localUrl(c.image)}" alt="${c.name}" width="1080" height="1080">
      </div>
      <div class="character-info">
        <h1>${c.name}</h1>
        <div id="launch">
          <button id="enter" hidden disabled>START AR</button>
          <a id="apple" class="quicklook" rel="ar" hidden aria-label="View ${c.name} in AR">
            <img src="${localUrl(c.image)}" alt="View in AR">
          </a>
          <button id="retry" hidden>TRY AGAIN</button>
        </div>
        <p class="status" id="status" role="status">Getting your character ready…</p>
        <p class="status" id="preview-status" role="status"></p>
        <div id="share" hidden>
          <canvas id="qr" width="180" height="180"
            aria-label="Scan to open this character on your phone"></canvas>
          <p class="status">Scan to open on your phone</p>
          <button id="copy">COPY LINK</button>
        </div>
      </div>
    </div>
    <nav class="character-nav" aria-label="Other characters">
      <a href="${versioned(`characters/${previous.id}/index.html`)}">← ${previous.name.toUpperCase()}</a>
      <a href="${versioned(`characters/${next.id}/index.html`)}">${next.name.toUpperCase()} →</a>
    </nav>`;
  const { detectPlatform, available } = await import(versioned('js/platform.js'));
  const config = { ...window.IMABOX_DEFAULTS, ...c },
    $ = (id) => document.getElementById(id);
  const asset = (path) => {
    const url = new URL(path, siteRoot);
    url.searchParams.set('v', c.assetRevision);
    return url.href;
  };
  const glbCheck = available(asset(c.glb)),
    usdzCheck = available(asset(c.usdz));
  const route = await detectPlatform();
  const usdzState = route === 'apple' ? await usdzCheck : 'unknown';
  if (route === 'apple') {
    // Only a definite 404 hides the button. A failed check is not proof the file
    // is gone, and hiding AR on a dropped HEAD request left iPhone visitors with
    // no way in at all. The canonical URL is sent without the cache-busting query
    // so Quick Look's share sheet points at a clean page address.
    if (usdzState !== 'missing') {
      $('apple').href =
        asset(c.usdz) + '#canonicalWebPageURL=' + location.origin + location.pathname;
      $('apple').hidden = false;
      $('status').textContent =
        'Tap View in AR, then point at the floor and drag your character where you want it.';
    } else {
      $('status').textContent = 'This character’s iPhone AR version is not available yet.';
      $('retry').hidden = false;
    }
  } else if (route === 'webxr') {
    $('status').textContent = 'Loading your character…';
  } else {
    $('status').textContent =
      route === 'apple-inapp'
        ? 'Tap the ••• menu and choose Open in Safari — AR does not run inside this app’s browser.'
        : route === 'apple-browser'
          ? 'Open this page in Safari on your iPhone or iPad for AR.'
          : route === 'android-browser'
            ? 'Open this page in Chrome on your Android phone for AR.'
            : route === 'android-unavailable'
              ? 'AR is unavailable here. Open in Chrome on an ARCore-compatible phone, with Google Play Services for AR installed.'
              : 'Open on your phone to bring this character into your space.';
    $('share').hidden = false;
    try {
      const { default: QR } = await import(versioned('vendor/qrcode.js'));
      await QR.toCanvas($('qr'), location.href, { width: 180, margin: 2 });
    } catch {
      $('qr').hidden = true;
    }
  }
  $('copy').onclick = async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      $('copy').textContent = 'LINK COPIED';
    } catch {
      $('preview-status').textContent = 'Copy this page’s address from the address bar.';
    }
  };
  $('retry').onclick = () => location.reload();
  const glbState = await glbCheck;
  if (glbState === 'missing') {
    $('preview-status').textContent = '3D preview coming soon.';
    if (route === 'webxr') {
      $('retry').hidden = false;
      $('status').textContent = 'This character’s Android and 3D version is not available yet.';
    }
    return;
  }
  // The drag-to-look preview loads on every platform. On Apple it is extra:
  // View in AR opens the USDZ in Quick Look and never waits for the GLB or
  // WebGL, so a preview failure there just leaves the poster in place.
  const apple = route === 'apple' || route === 'apple-browser' || route === 'apple-inapp';
  try {
    const { mountExperience } = await import(versioned('js/experience.js'));
    await mountExperience({
      config,
      url: asset(c.glb),
      route,
      art: $('art'),
      enter: $('enter'),
      setStatus: (text) => ($('preview-status').textContent = text),
    });
    if (route === 'webxr')
      $('status').textContent = 'Choose a clear, level floor with room for the approach.';
  } catch (error) {
    console.error(error);
    if (apple) return;
    $('preview-status').textContent = `The 3D experience could not load. ${error.message}`;
    $('retry').hidden = false;
  }
}
init().catch((error) => {
  console.error(error);
  const target = document.querySelector('#status') || document.querySelector('#gallery');
  target.textContent = 'We couldn’t load the characters. Refresh to try again.';
});
