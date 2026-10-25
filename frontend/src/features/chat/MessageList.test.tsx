import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { MessageList } from './MessageList';
import type { ChatMessage } from '../../shared/api/types';
import { api } from '../../shared/api/client';

describe('MessageList', () => {
  it('keeps one live status and approval card for the same background run', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({id: 'RR-test', status: 'APPROVAL_PENDING'});
    renderWithProviders(<MessageList messages={[
      {id: 'progress', role: 'assistant', run_id: 'RR-test', content: 'Current run progress'},
      {id: 'ack', role: 'assistant', run_id: 'RR-test', content: 'Duplicate initial acknowledgment'},
    ]} />);
    expect(screen.getByText('Current run progress')).toBeInTheDocument();
    expect(screen.queryByText('Duplicate initial acknowledgment')).not.toBeInTheDocument();
    expect(screen.getAllByLabelText('Run RR-test')).toHaveLength(1);
    vi.restoreAllMocks();
  });
  it('renders ChatGPT-style empty state greeting when no messages', () => {
    const onQuickSend = vi.fn();
    renderWithProviders(<MessageList messages={[]} onQuickSend={onQuickSend} />);
    expect(screen.getByText(/Hôm nay chúng ta bắt đầu từ đâu/i)).toBeInTheDocument();
    expect(screen.getByText('Đề cương 5 cấp')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Đề cương 5 cấp'));
    expect(onQuickSend).toHaveBeenCalledWith(expect.stringContaining('/outline'));
  });

  it('renders messages, citations and supports pinning messages', () => {
    const messages: ChatMessage[] = [
      {
        id: 'msg-1',
        role: 'user',
        content: 'What are the main gaps in image restoration?',
        text: 'What are the main gaps in image restoration?',
      },
      {
        id: 'msg-2',
        role: 'assistant',
        content: 'Recent papers highlight diffusion trade-offs and high compute demand.',
        text: 'Recent papers highlight diffusion trade-offs and high compute demand.',
        citations: [{ key: '1', title: 'Diffusion Models for MRI 2025' }],
        pinned: false,
      },
    ];

    const onPinMessage = vi.fn();
    renderWithProviders(
      <MessageList messages={messages} onPinMessage={onPinMessage} />
    );

    expect(screen.getByText('What are the main gaps in image restoration?')).toBeInTheDocument();
    expect(screen.getByText(/Recent papers highlight/i)).toBeInTheDocument();
    expect(screen.getByText('[1] Diffusion Models for MRI 2025')).toBeInTheDocument();

    const pinBtns = screen.getAllByTitle('Ghim tin nhắn');
    fireEvent.click(pinBtns[1]);
    expect(onPinMessage).toHaveBeenCalledWith('msg-2', true);
  });

  it('renders streaming indicator when streaming', () => {
    renderWithProviders(
      <MessageList
        messages={[]}
        isStreaming={true}
        streamingText="Thinking and formulating response..."
      />
    );
    expect(screen.getByText(/Đang suy luận…/i)).toBeInTheDocument();
    expect(screen.getByText('Thinking and formulating response...')).toBeInTheDocument();
  });
});
