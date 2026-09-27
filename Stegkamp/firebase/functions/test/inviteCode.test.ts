import { describe, expect, it } from "vitest";
import {
  CODE_ALPHABET,
  generateInviteCode,
  isValidInviteCode,
  normalizeInviteCode,
} from "../src/lib/inviteCode.js";

describe("inviteCode", () => {
  it("generates valid six-character codes", () => {
    for (let i = 0; i < 500; i++) {
      const code = generateInviteCode();
      expect(code).toHaveLength(6);
      expect(isValidInviteCode(code)).toBe(true);
    }
  });

  it("uses the injected random source", () => {
    expect(generateInviteCode(() => 0)).toBe("AAAAAA");
    expect(generateInviteCode((max) => max - 1)).toBe("999999");
  });

  it("leaves out look-alike characters", () => {
    for (const c of "0O1IL") expect(CODE_ALPHABET).not.toContain(c);
  });

  it("normalizes user input", () => {
    expect(normalizeInviteCode("k7mx2q")).toBe("K7MX2Q");
    expect(normalizeInviteCode(" K7M-X2Q ")).toBe("K7MX2Q");
  });

  it.each(["", "K7MX2", "K7MX2QQ", "K7MX0Q", "K7MXIQ", "K7MX2!"])("rejects %j", (input) => {
    expect(normalizeInviteCode(input)).toBeNull();
  });
});
