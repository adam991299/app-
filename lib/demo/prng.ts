/** Tiny deterministic PRNG so demo-mode "friend activity" is stable across renders/days
 * instead of re-randomizing on every screen visit. Not cryptographic — just seeded fun. */
function hashString(input: string): number {
  let h = 1779033703 ^ input.length;
  for (let i = 0; i < input.length; i++) {
    h = Math.imul(h ^ input.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return h >>> 0;
}

function mulberry32(seed: number) {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function seededRandom(seedKey: string): () => number {
  return mulberry32(hashString(seedKey));
}

export function seededInt(seedKey: string, min: number, max: number): number {
  const r = seededRandom(seedKey)();
  return Math.floor(r * (max - min + 1)) + min;
}

export function seededBool(seedKey: string, trueProbability = 0.5): boolean {
  return seededRandom(seedKey)() < trueProbability;
}

export function seededPick<T>(seedKey: string, items: T[]): T {
  return items[seededInt(seedKey, 0, items.length - 1)];
}
