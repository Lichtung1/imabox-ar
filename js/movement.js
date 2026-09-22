// Kept independent from animation playback. A stopped approach never stops time.
export function approachProgress(time, interval) {
  if (!interval) return 0;
  if (interval.keyframes) {
    const points = interval.keyframes;
    if (time <= points[0][0]) return points[0][1];
    for (let i = 1; i < points.length; i++) {
      const [t, p] = points[i],
        [previousT, previousP] = points[i - 1];
      if (time <= t) return previousP + ((p - previousP) * (time - previousT)) / (t - previousT);
    }
    return points.at(-1)[1];
  }
  return Math.max(0, Math.min(1, (time - interval.start) / (interval.end - interval.start)));
}
export function stopBeforeViewer(from, to, viewer, radius) {
  const fx = from.x - viewer.x,
    fz = from.z - viewer.z,
    dx = to.x - from.x,
    dz = to.z - from.z;
  const c = fx * fx + fz * fz - radius * radius;
  if (c <= 1e-8) return { fraction: 0, stopped: true };
  const a = dx * dx + dz * dz,
    b = 2 * (fx * dx + fz * dz),
    discriminant = b * b - 4 * a * c;
  if (a > 1e-12 && discriminant >= 0) {
    const t = (-b - Math.sqrt(discriminant)) / (2 * a);
    if (t >= 0 && t <= 1) return { fraction: t, stopped: true };
  }
  return { fraction: 1, stopped: false };
}
