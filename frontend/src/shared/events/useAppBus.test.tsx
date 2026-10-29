import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAppBus } from './useAppBus';
import { createTestQueryClient } from '../../test/test-utils';
import React from 'react';
import { QueryClientProvider } from '@tanstack/react-query';

describe('useAppBus', () => {
  let mockEventSourceInstance: any;

  beforeEach(() => {
    vi.restoreAllMocks();

    mockEventSourceInstance = {
      url: '',
      onopen: null,
      onmessage: null,
      onerror: null,
      close: vi.fn(),
    };

    class MockEventSource {
      url: string;
      onopen: any = null;
      onmessage: any = null;
      onerror: any = null;
      close = vi.fn();
      constructor(url: string) {
        this.url = url;
        mockEventSourceInstance = this;
      }
    }

    (globalThis as any).EventSource = MockEventSource;
  });

  it('connects to SSE stream, updates connection state, and handles messages', async () => {
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result, unmount } = renderHook(() => useAppBus(), { wrapper });

    expect(mockEventSourceInstance.url).toContain('/api/events/stream');

    // Simulate open
    act(() => {
      mockEventSourceInstance.onopen?.();
    });
    expect(result.current.isConnected).toBe(true);

    // Simulate research.mission event
    act(() => {
      mockEventSourceInstance.onmessage?.({
        data: JSON.stringify({ seq: 1, type: 'research.mission', mission_id: 'm-1' }),
      });
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['missions'] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['autonomy'] });  // Workflows L1–L4 refresh too (v6.6.4)

    // Simulate aiws session event
    act(() => {
      mockEventSourceInstance.onmessage?.({
        data: JSON.stringify({ seq: 2, type: 'aiws.chat', session_id: 's-1' }),
      });
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['sessions'] });

    // Simulate run event
    act(() => {
      mockEventSourceInstance.onmessage?.({
        data: JSON.stringify({ seq: 3, type: 'run.step', run_id: 'r-1' }),
      });
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['runs'] });

    // Simulate api.mutation event
    act(() => {
      mockEventSourceInstance.onmessage?.({
        data: JSON.stringify({ seq: 4, type: 'api.mutation' }),
      });
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['dashboard'] });

    // Simulate error
    act(() => {
      mockEventSourceInstance.onerror?.();
    });
    expect(result.current.isConnected).toBe(false);
    expect(mockEventSourceInstance.close).toHaveBeenCalled();

    // Clean unmount
    unmount();
  });
});
