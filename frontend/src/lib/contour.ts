// Topographic contour lines, generated from a seed so every place and destination gets its own terrain.

function rng(seed: string) {
  let h = 1779033703 ^ seed.length;
  for (let i = 0; i < seed.length; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return () => {
    h = Math.imul(h ^ (h >>> 16), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  };
}

export function contourPaths(seed: string, rings = 9, w = 400, h = 300): string[] {
  const rand = rng(seed);
  const cx = w * (0.25 + rand() * 0.5);
  const cy = h * (0.25 + rand() * 0.5);
  const waves = Array.from({ length: 4 }, (_, k) => ({ k: k + 2, a: 0.07 + rand() * 0.11, p: rand() * Math.PI * 2 }));
  const squash = 0.7 + rand() * 0.5;
  const paths: string[] = [];
  for (let r = 0; r < rings; r++) {
    const base = 14 + r * (Math.max(w, h) / (rings * 1.45));
    const pts: string[] = [];
    for (let i = 0; i <= 72; i++) {
      const t = (i / 72) * Math.PI * 2;
      let rad = base;
      for (const { k, a, p } of waves) rad *= 1 + a * Math.sin(k * t + p + r * 0.18);
      const x = cx + Math.cos(t) * rad;
      const y = cy + Math.sin(t) * rad * squash;
      pts.push(`${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`);
    }
    paths.push(pts.join("") + "Z");
  }
  return paths;
}
