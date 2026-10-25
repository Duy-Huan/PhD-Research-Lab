import type { ChatSession } from '../../shared/api/types';

export async function waitForChatTurn(
  read: () => Promise<ChatSession>, turnId: string, timeoutMs = 900_000, intervalMs = 700
) {
  const deadline = Date.now() + timeoutMs;
  while (true) {
    const session = await read();
    const turn = session.turns?.find(t => t.id === turnId);
    if (turn?.status === 'failed') throw new Error(turn.error || 'Chat turn failed. Check provider status.');
    if (turn?.status === 'cancelled') throw new Error('Chat turn was cancelled.');
    if (turn && ['completed', 'waiting_approval', 'awaiting_launch'].includes(turn.status)) return { session, turn };
    if (Date.now() >= deadline) throw new Error('Still waiting for the agent. Check the conversation status or cancel the turn before retrying.');
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
}
