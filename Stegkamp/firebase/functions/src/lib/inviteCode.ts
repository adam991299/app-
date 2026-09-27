import { randomInt } from "node:crypto";

/**
 * Six-character join codes such as "K7MX2Q". The alphabet leaves out look-alikes (0/O, 1/I/L) and
 * must stay in sync with `CompetitionCode` in the iOS app (Packages/StegkampKit).
 */
export const CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
export const CODE_LENGTH = 6;

export function generateInviteCode(random: (max: number) => number = randomInt): string {
  let code = "";
  for (let i = 0; i < CODE_LENGTH; i++) {
    code += CODE_ALPHABET[random(CODE_ALPHABET.length)];
  }
  return code;
}

export function isValidInviteCode(code: string): boolean {
  return code.length === CODE_LENGTH && [...code].every((c) => CODE_ALPHABET.includes(c));
}

/** Uppercases and strips spaces and dashes; returns null for anything that is not a valid code. */
export function normalizeInviteCode(input: string): string | null {
  const cleaned = input.toUpperCase().replace(/[\s-]/g, "");
  return isValidInviteCode(cleaned) ? cleaned : null;
}
