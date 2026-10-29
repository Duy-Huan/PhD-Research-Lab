import { describe, it, expect, beforeEach } from 'vitest';
import { rememberTopic, rememberedTopic, useUIStore } from './uiStore';

// v6.6.4 (A8): the selected Topic survives a reload, per project folder; storage failures never break the app.
describe('remembered Topic', () => {
  beforeEach(() => {
    localStorage.clear();
    useUIStore.setState({ project: { data_dir: 'D:/p1' } as never, activeTopic: null, activeTopicId: null, topics: [] });
  });

  it('remembers the selected Topic per project folder and forgets it when cleared', () => {
    useUIStore.getState().setActiveTopic({ id: 't-1', title: 'One' } as never);
    expect(rememberedTopic('D:/p1')).toBe('t-1');
    expect(rememberedTopic('D:/p2')).toBeNull();
    useUIStore.getState().setActiveTopicId(null);
    expect(rememberedTopic('D:/p1')).toBeNull();
  });

  it('keeps working when browser storage is unavailable', () => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = () => { throw new Error('blocked'); };
    try {
      expect(() => rememberTopic('D:/p1', 't-1')).not.toThrow();
      expect(() => useUIStore.getState().setActiveTopic({ id: 't-2', title: 'Two' } as never)).not.toThrow();
      expect(useUIStore.getState().activeTopicId).toBe('t-2');
    } finally {
      Storage.prototype.setItem = original;
    }
    expect(rememberedTopic(undefined)).toBeNull();
  });
});
