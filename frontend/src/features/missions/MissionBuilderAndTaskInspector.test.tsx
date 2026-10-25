import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { MissionBuilder } from './MissionBuilder';
import { TaskInspector } from './TaskInspector';
import { MissionDAG } from './MissionDAG';
import { api } from '../../shared/api/client';
import type { MissionTask } from '../../shared/api/types';

describe('MissionBuilder, TaskInspector & MissionDAG', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders MissionBuilder form, adds/removes tasks, and submits draft', async () => {
    const onSuccess = vi.fn();
    const onCancel = vi.fn();
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      id: 'mission-created-1',
      topic_id: 'topic-1',
      objective: 'Synthetic Benchmarking',
    });

    const { container } = renderWithProviders(
      <MissionBuilder topicId="topic-1" onSuccess={onSuccess} onCancel={onCancel} />
    );

    expect(screen.getByText(/Tạo Nhiệm vụ Nghiên cứu/i)).toBeInTheDocument();

    // Add a step
    fireEvent.click(screen.getByText(/Thêm Task/i));
    const stepInputs = screen.getAllByPlaceholderText(/Task ID/i);
    expect(stepInputs.length).toBeGreaterThanOrEqual(3);

    // Remove a step
    const trashButtons = container.querySelectorAll('button.icon');
    if (trashButtons.length > 0) {
      fireEvent.click(trashButtons[0]);
    }

    // Fill objective
    const objInput = screen.getByPlaceholderText(/Tổng hợp bằng chứng/i);
    fireEvent.change(objInput, { target: { value: 'Synthetic Benchmarking' } });

    // Submit
    const submitBtn = screen.getByText(/Tạo Mission Draft/i);
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        '/api/research/topics/topic-1/missions',
        expect.objectContaining({
          objective: 'Synthetic Benchmarking',
        })
      );
      expect(onSuccess).toHaveBeenCalled();
    });
    // MissionSpec.Limits permits at most three calls; a successful mocked POST must
    // not conceal a form payload that the real API rejects with 422.
    const body = postSpy.mock.calls[0][1] as { limits: { max_reasoning_calls: number } };
    expect(body.limits.max_reasoning_calls).toBeLessThanOrEqual(3);

    // Cancel button
    fireEvent.click(screen.getByText(/Huỷ/i));
    expect(onCancel).toHaveBeenCalled();
  });

  it('submits mission from JSON mode and handles invalid JSON', async () => {
    const onSuccess = vi.fn();
    const onCancel = vi.fn();
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({ id: 'm-json' });
    window.alert = vi.fn();

    const { container } = renderWithProviders(
      <MissionBuilder topicId="topic-1" onSuccess={onSuccess} onCancel={onCancel} />
    );

    // Toggle JSON mode
    fireEvent.click(screen.getByText(/Chế độ JSON/i));
    expect(screen.getByText(/Chế độ Form/i)).toBeInTheDocument();

    // Valid JSON submit
    fireEvent.click(screen.getByText(/Tạo Mission Draft/i));
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalled();
      expect(onSuccess).toHaveBeenCalled();
    });

    // Invalid JSON submit
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: '{ invalid json' } });
    fireEvent.click(screen.getByText(/Tạo Mission Draft/i));
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Cú pháp JSON không hợp lệ'));
  });

  it('renders TaskInspector tabs and details', () => {
    const onClose = vi.fn();
    const dummyTask: MissionTask = {
      id: 'task-100',
      status: 'completed',
      payload: {
        spec: {
          id: 'task-100',
          capability: 'paper.inspect',
          preferred_engine: 'deterministic',
          depends_on: [],
          args: { paper_id: 'p-1' },
        },
        attempts: 1,
        result: {
          output: 'Extracted key contributions',
        },
        execution_record: {
          attempt_key: 'att-1',
          elapsed_seconds: 4.5,
          outcome: 'success',
          provider_usage: {},
          verification_status: 'verified',
        },
      },
    };

    const { container, rerender } = renderWithProviders(
      <TaskInspector task={dummyTask} onClose={onClose} />
    );

    expect(screen.getByText(/Chi tiết nhiệm vụ: task-100/i)).toBeInTheDocument();

    // Switch to Kết quả / Logs tab
    fireEvent.click(screen.getByText(/Kết quả \/ Logs/i));
    expect(screen.getByText(/Extracted key contributions/i)).toBeInTheDocument();

    // Switch to Đầu vào tab
    fireEvent.click(screen.getByText('Đầu vào'));
    expect(screen.getByText(/"paper_id": "p-1"/i)).toBeInTheDocument();

    // Switch to Kiểm thử & Bằng chứng tab
    fireEvent.click(screen.getByText(/Kiểm thử & Bằng chứng/i));
    expect(screen.getByText(/Xác minh độc lập/i)).toBeInTheDocument();

    // Test close button
    const closeBtn = container.querySelector('button.icon');
    if (closeBtn) fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();

    // When task is null
    rerender(<TaskInspector task={null} onClose={onClose} />);
    expect(screen.queryByText(/Chi tiết nhiệm vụ: task-100/i)).not.toBeInTheDocument();
  });

  it('renders MissionDAG with all task statuses and triggers onSelectTask on click', () => {
    const onSelectTask = vi.fn();
    const dummyTasks: MissionTask[] = [
      {
        id: 'task-1',
        status: 'running',
        payload: { attempts: 1, spec: { id: 'step-1', capability: 'paper.discover', depends_on: [] } },
      },
      {
        id: 'task-2',
        status: 'completed',
        payload: { attempts: 1, spec: { id: 'step-2', capability: 'paper.inspect', depends_on: ['task-1'] } },
      },
      {
        id: 'task-3',
        status: 'failed',
        payload: { attempts: 1, spec: { id: 'step-3', capability: 'experiment.run', depends_on: ['task-2'] } },
      },
      {
        id: 'task-4',
        status: 'interrupted',
        payload: { attempts: 1, spec: { id: 'step-4', capability: 'mission.report', depends_on: ['task-2'] } },
      },
      {
        id: 'task-5',
        status: 'pending',
        payload: { attempts: 0, spec: { id: 'step-5', capability: 'artifact.verify', depends_on: [] } },
      },
    ];

    renderWithProviders(<MissionDAG tasks={dummyTasks} onSelectTask={onSelectTask} />);

    expect(screen.getByText('step-1')).toBeInTheDocument();
    expect(screen.getByText('step-2')).toBeInTheDocument();
    expect(screen.getByText('step-3')).toBeInTheDocument();
    expect(screen.getByText('step-4')).toBeInTheDocument();
    expect(screen.getByText('step-5')).toBeInTheDocument();

    fireEvent.click(screen.getByText('step-1'));
    expect(onSelectTask).toHaveBeenCalledWith('task-1');
  });
});
