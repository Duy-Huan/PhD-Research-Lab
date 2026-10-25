import { describe, expect, it, vi } from 'vitest';
import { waitForChatTurn } from './waitForChatTurn';

describe('CLI turn completion', () => {
  it('waits beyond the old 28 second cutoff and returns the matching turn', async () => {
    vi.useFakeTimers();
    try {
      let calls = 0;
      const result = waitForChatTurn(async () => ({id: 's', title: '', created: 0, updated: 0,
        turns: [{id: 't', status: ++calls < 45 ? 'running' : 'completed'}]}), 't');
      await vi.advanceTimersByTimeAsync(32_000);
      expect((await result).turn.status).toBe('completed');
    } finally { vi.useRealTimers(); }
  });

  it.each(['failed', 'cancelled'] as const)('shows %s instead of silently clearing the spinner', async status => {
    await expect(waitForChatTurn(async () => ({id: 's', title: '', created: 0, updated: 0,
      turns: [{id: 't', status, error: 'weekly limit'}]}), 't')).rejects.toThrow(status === 'failed' ? 'weekly limit' : 'cancelled');
  });

  it('does not mistake another turn for the requested reply', async () => {
    await expect(waitForChatTurn(async () => ({id: 's', title: '', created: 0, updated: 0,
      turns: [{id: 'other', status: 'completed'}]}), 't', 0)).rejects.toThrow('Still waiting');
  });
});
