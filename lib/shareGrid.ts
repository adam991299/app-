import type { QuestionGuess } from '@/types/database';

/** Wordle-style emoji grid for a completed question attempt. One square per guess slot
 * (3 total): 🟩 correct, 🟨 close, 🟥 far off, ⬜ unused (solved before all 3 guesses). */
export function questionShareGrid(guesses: QuestionGuess[], answer: number): string[] {
  const squares: string[] = [];
  for (let i = 0; i < 3; i++) {
    const guess = guesses[i];
    if (!guess) {
      squares.push('⬜');
      continue;
    }
    if (guess.direction === 'correct') {
      squares.push('🟩');
      continue;
    }
    const proximity = Math.abs(guess.value - answer) / Math.max(Math.abs(answer), 1);
    squares.push(proximity <= 0.1 ? '🟨' : '🟥');
  }
  return squares;
}

/** Single-square rating for a puzzle attempt: 🟩 solved fast, 🟨 solved, 🟥 not solved. */
export function puzzleShareGrid(solved: boolean, timeSeconds: number): string[] {
  if (!solved) return ['🟥'];
  return [timeSeconds <= 30 ? '🟩' : '🟨'];
}
