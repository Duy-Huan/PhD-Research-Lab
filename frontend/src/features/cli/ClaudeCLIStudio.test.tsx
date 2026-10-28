import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor, within } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { ClaudeCLIStudio, CLI_SESSION_KEY } from './ClaudeCLIStudio';
import { useUIStore } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';

// FQC-CLI-STUDIO-663: the CLI studio fills the main area, keeps its prompt at the bottom, frames the transcript and
// every AI answer, and sends turns to the provider the researcher selected (from the backend catalog).
const PROVIDERS = [
  { id: 'cli:codex', label: 'ChatGPT (OpenAI Codex CLI)', transport: 'cli', state: 'CONNECTED', detail: 'signed in with ChatGPT', available: true },
  { id: 'cli:claude_code', label: 'Claude (Claude Code CLI)', transport: 'cli', state: 'CONNECTED', detail: 'sign-in configured', available: true },
  { id: 'cli:gemini_cli', label: 'Gemini CLI', transport: 'cli', state: 'AUTH_EXPIRED', detail: 'Run `gemini` and sign in', available: false },
  { id: 'app:openai', label: 'OpenAI API', transport: 'app', state: 'READY', available: true },
];

let session: any;
function mockBackend(extra: (url: string) => any = () => undefined) {
  vi.spyOn(api, 'get').mockImplementation(async (url: string) => {
    const hit = extra(url);
    if (hit !== undefined) return hit;
    if (url === '/api/config') return { version: '6.6.3', agent_models: { assistant: 'gpt-5' } };
    if (url === '/api/models') return { providers: PROVIDERS, agent_catalog: { assistant: { engine: 'auto', selected: '' } } };
    if (url === '/api/skills') return { skills: [{ name: 'lit', title: 'Literature from backend', description: 'A real registered command' }] };
    if (url.startsWith('/api/chat/sessions/')) return session;
    if (url.startsWith('/api/runs/')) return { status: 'COMPLETED' };
    return {};
  });
}

describe('ClaudeCLIStudio', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    useUIStore.getState().setLanguage('vi');
    useUIStore.setState({ selectedCliProvider: 'claude_code' });
    session = { id: 'sess-cli', messages: [], turns: [], approvals: [] };
  });

  it('frames the transcript and keeps the prompt as the last block of the studio', async () => {
    mockBackend();
    const { container } = renderWithProviders(<ClaudeCLIStudio />);
    const transcript = screen.getByRole('log', { name: 'Hội thoại CLI' });
    const prompt = screen.getByRole('form', { name: 'Lệnh CLI' });
    const root = container.firstElementChild as HTMLElement;
    expect(screen.getByRole('status')).toHaveTextContent('Đang kiểm tra các công cụ CLI');
    expect(screen.getByText(/gửi tới Claude Code$/)).toBeInTheDocument();
    expect(root.lastElementChild).toBe(prompt);
    expect(transcript.compareDocumentPosition(prompt) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(transcript.style.border).toContain('1px solid');
    expect(root.style.background).toBe('var(--bg)');
    expect(container.innerHTML).not.toMatch(/#0d1117|#161b22/);
  });

  it('lists CLI providers from the backend, explains unavailable ones, and sends the turn to the chosen one', async () => {
    const post = vi.spyOn(api, 'post').mockImplementation(async (url: string) =>
      url === '/api/chat/sessions' ? { id: 'sess-cli' } : { id: 'turn-1', status: 'running' });
    session = { id: 'sess-cli', turns: [{ id: 'turn-1', status: 'completed' }], approvals: [],
      messages: [{ id: 'm1', role: 'user', content: 'Tìm hiểu PINNs', turn_id: 'turn-1' },
        { id: 'm2', role: 'assistant', content: 'PINNs giải PDE bằng mạng nơ-ron.', turn_id: 'turn-1', run_id: 'run-7' }] };
    mockBackend();
    renderWithProviders(<ClaudeCLIStudio />);

    const gemini = await screen.findByRole('radio', { name: /Gemini CLI/ });
    expect(gemini).toBeDisabled();
    expect(gemini.closest('label')).toHaveAttribute('title', expect.stringContaining('gemini'));
    expect(screen.queryByRole('radio', { name: /OpenAI API/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('radio', { name: /Codex/ }));
    expect(useUIStore.getState().selectedCliProvider).toBe('codex');

    const input = screen.getByRole('textbox', { name: 'Lệnh CLI' });
    fireEvent.change(input, { target: { value: 'Tìm hiểu PINNs' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/chat/sessions/sess-cli/turns',
      expect.objectContaining({ text: 'Tìm hiểu PINNs', overrides: expect.objectContaining({ provider: 'cli:codex' }) })));
    const answer = await screen.findByRole('article', { name: 'Câu trả lời AI' });
    expect(within(answer).getByText(/PINNs giải PDE/)).toBeInTheDocument();
    expect(answer.style.border).toContain('1px solid');
    expect(await within(answer).findByRole('complementary', { name: 'Run run-7' })).toBeInTheDocument();
    expect(localStorage.getItem(CLI_SESSION_KEY)).toBe('sess-cli');
  });

  it('keeps the provider on the conversation so cmd and the web use the same one', async () => {
    const post = vi.spyOn(api, 'post').mockImplementation(async (url: string) =>
      url === '/api/chat/sessions' ? { id: 'sess-cli' } : { id: 'turn-1' });
    session = { id: 'sess-cli', settings: {}, approvals: [], turns: [{ id: 'turn-1', status: 'completed' }], messages: [] };
    mockBackend();
    renderWithProviders(<ClaudeCLIStudio />);
    fireEvent.click(await screen.findByRole('radio', { name: /Codex/ }));
    const input = screen.getByRole('textbox', { name: 'Lệnh CLI' });
    fireEvent.change(input, { target: { value: 'xin chào' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/chat/sessions', { settings: { provider: 'cli:codex' } }));

    const put = vi.spyOn(api, 'put').mockResolvedValue({});
    fireEvent.click(screen.getByRole('radio', { name: /Claude Code/ }));
    await waitFor(() => expect(put).toHaveBeenCalledWith('/api/chat/sessions/sess-cli', { settings: { provider: 'cli:claude_code' } }));
  });

  it('follows a provider chosen in cmd and labels each answer with the provider that wrote it', async () => {
    localStorage.setItem(CLI_SESSION_KEY, 'sess-cli');
    session = { id: 'sess-cli', settings: { provider: 'cli:codex' }, turns: [], approvals: [],
      messages: [{ id: 'm1', role: 'assistant', content: 'Từ Claude.', provider: 'cli:claude_code' }] };
    mockBackend();
    renderWithProviders(<ClaudeCLIStudio />);
    await waitFor(() => expect(useUIStore.getState().selectedCliProvider).toBe('codex'));
    const answer = await screen.findByRole('article', { name: 'Câu trả lời AI' });
    await waitFor(() => expect(answer).toHaveTextContent('Claude (Claude Code CLI)'));
  });

  it('reopens the saved CLI session after a reload', async () => {
    localStorage.setItem(CLI_SESSION_KEY, 'sess-cli');
    session = { id: 'sess-cli', turns: [], approvals: [],
      messages: [{ id: 'm1', role: 'user', content: '/lit diffusion' }, { id: 'm2', role: 'assistant', content: 'Found 12 papers.' }] };
    mockBackend();
    renderWithProviders(<ClaudeCLIStudio />);
    expect(await screen.findByText('Found 12 papers.')).toBeInTheDocument();
    expect(screen.getByText('/lit diffusion')).toBeInTheDocument();
  });

  it('offers the launch action for a manual turn and shows failures inline', async () => {
    localStorage.setItem(CLI_SESSION_KEY, 'sess-cli');
    const post = vi.spyOn(api, 'post').mockImplementation(async (url: string) =>
      url.endsWith('/turns') ? { id: 'turn-2' } : {});
    session = { id: 'sess-cli', messages: [], approvals: [], turns: [{ id: 'turn-2', status: 'awaiting_launch' }] };
    mockBackend();
    renderWithProviders(<ClaudeCLIStudio />);
    const input = screen.getByRole('textbox', { name: 'Lệnh CLI' });
    fireEvent.change(input, { target: { value: 'chạy thủ công' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    fireEvent.click(await screen.findByRole('button', { name: 'Khởi chạy' }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/chat/sessions/sess-cli/turns/turn-2/launch', {}));

    session = { ...session, turns: [...session.turns, { id: 'turn-3', status: 'failed', error: 'Codex sign-in expired' }] };
    post.mockImplementation(async (url: string) => (url.endsWith('/turns') ? { id: 'turn-3' } : {}));
    fireEvent.change(input, { target: { value: 'thử lại' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(await screen.findByRole('alert')).toHaveTextContent('Codex sign-in expired');
  });

  it('lists each pending approval and reports what /accept all approved', async () => {
    localStorage.setItem(CLI_SESSION_KEY, 'sess-cli');
    const post = vi.spyOn(api, 'post').mockImplementation(async (url: string) => (url.endsWith('/turns') ? { id: 'turn-4' } : {}));
    session = { id: 'sess-cli', messages: [], turns: [{ id: 'turn-4', status: 'waiting_approval' }],
      approvals: [{ id: 'ap-1', name: 'experiment.run', reason: 'Train 3 seeds', status: 'pending' },
        { id: 'ap-2', name: 'files.write', reason: 'Save metrics.json', status: 'pending' }] };
    mockBackend();
    renderWithProviders(<ClaudeCLIStudio />);
    const input = screen.getByRole('textbox', { name: 'Lệnh CLI' });
    fireEvent.change(input, { target: { value: 'chạy thí nghiệm' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    const list = await screen.findByRole('list', { name: 'Chờ duyệt' });
    expect(within(list).getAllByRole('listitem').map(li => li.textContent)).toEqual([
      expect.stringContaining('experiment.run'), expect.stringContaining('files.write')]);
    fireEvent.click(within(list).getAllByRole('button', { name: 'Duyệt' })[0]);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/chat/sessions/sess-cli/approvals/ap-1', { decision: 'approve' }));

    fireEvent.change(input, { target: { value: '/accept all' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(await screen.findByText(/Đã duyệt: experiment\.run, files\.write/)).toBeInTheDocument();
  });

  it('uses the active language for every label and the backend command catalog', async () => {
    useUIStore.getState().setLanguage('en');
    mockBackend();
    renderWithProviders(<ClaudeCLIStudio />);
    expect(screen.getByRole('button', { name: /Literature \/lit/ })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Khảo sát|Đề cương|Thực nghiệm|Bài báo|Phản biện|Quy trình|Xoá màn hình/);
    const input = screen.getByRole('textbox', { name: 'CLI command' });
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/api/skills'));
    fireEvent.change(input, { target: { value: '/workflow list' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(await screen.findByText(/Literature from backend/)).toBeInTheDocument();
  });

  it('shows errors inline instead of a browser alert', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    vi.spyOn(api, 'post').mockRejectedValue(new Error('backend offline'));
    mockBackend();
    renderWithProviders(<ClaudeCLIStudio />);
    fireEvent.click(screen.getByRole('button', { name: 'Phiên mới' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('backend offline');
    expect(alertSpy).not.toHaveBeenCalled();
  });

  it('continues this conversation in cmd and offers the command to copy', async () => {
    localStorage.setItem(CLI_SESSION_KEY, 'sess-cli');
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const post = vi.spyOn(api, 'post').mockResolvedValue({ launched: true, command: 'chat.bat --session sess-cli' });
    mockBackend();
    renderWithProviders(<ClaudeCLIStudio />);
    fireEvent.click(screen.getByRole('button', { name: /Mở trong (cmd|terminal)/ }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/chat/sessions/sess-cli/console', {}));
    expect(await screen.findByText('chat.bat --session sess-cli')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sao chép lệnh' }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('chat.bat --session sess-cli'));
  });

  it('launches the selected CLI in an external terminal', async () => {
    mockBackend();
    const post = vi.spyOn(api, 'post').mockResolvedValue({ ok: true });
    renderWithProviders(<ClaudeCLIStudio />);
    fireEvent.click(await screen.findByRole('radio', { name: /Codex/ }));
    fireEvent.click(screen.getByRole('button', { name: /Mở terminal ngoài/ }));
    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/providers/codex/launch', { terminal: true }));
  });
});

describe('Chat CLI entry point', () => {
  it('opens the CLI studio in the main area instead of the side drawer', () => {
    useUIStore.setState({ mainView: 'chat', drawerKind: 'library' });
    useUIStore.getState().openDrawer('cli');
    expect(useUIStore.getState()).toMatchObject({ mainView: 'cli', drawerKind: null });
    useUIStore.getState().openDrawer('cli', 'codex');
    expect(useUIStore.getState()).toMatchObject({ mainView: 'cli', drawerKind: null, selectedCliProvider: 'codex' });
  });
});
