import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { api } from '../../shared/api/client';
import { useUIStore } from '../../shared/state/uiStore';
import { NativeExperimentTracking } from './NativeExperimentTracking';
import { OpenCodePanel } from '../opencode/OpenCodePanel';

describe('Native experiment interface (controlled HTTP fixtures)', () => {
  let runs: any[];
  beforeEach(() => {
    vi.restoreAllMocks(); useUIStore.getState().setLanguage('en');
    runs = [];
    vi.spyOn(api, 'get').mockImplementation(async url => url === '/api/tracking/runs'
      ? {process_runs: [{run_id: 'process-1', status: 'failed', metrics: {loss: 9}}], protocol_runs: []}
      : {runs});
    vi.spyOn(api, 'post').mockResolvedValue({});
  });

  it('keeps failed process evidence visible and scientific verification separate', async () => {
    renderWithProviders(<NativeExperimentTracking />);
    expect(await screen.findByText('process-1: failed')).toBeInTheDocument();
    expect(screen.getByText(/scientific verification are tracked separately/)).toBeInTheDocument();
    expect(screen.queryByText('ClearML')).not.toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('does not expose transfer/download/import before bundle approval', async () => {
    runs = [{run_id:'rc-123456789abc', backend:'native', status:'awaiting_approval', approvals: [], metrics: {}}];
    renderWithProviders(<NativeExperimentTracking />);
    expect(await screen.findByRole('button', {name:'Approve code transfer'})).toBeInTheDocument();
    expect(screen.queryByRole('link', {name:'Download approved bundle'})).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Import results.zip')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name:'Approve code transfer'}));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/compute/runs/rc-123456789abc/approve', {}));
  });

  it('submits explicit files, entrypoint, dataset hashes and required artifacts', async () => {
    renderWithProviders(<NativeExperimentTracking />);
    fireEvent.change(screen.getByLabelText('Dataset manifest JSON: path and sha256'), {target: {value:JSON.stringify([{path:'train.bin',sha256:'a'.repeat(64)}])}});
    fireEvent.click(screen.getByRole('button',{name:'Prepare for review'}));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/api/compute/runs', {
      files:['train.py','requirements.txt'],entrypoint:'train.py',required_artifacts:['metrics.json','best.pt'],
      dataset_manifest:[{path:'train.bin',sha256:'a'.repeat(64)}],compute_target:'colab-gpu',
    }));
  });

  it('invalid dataset JSON fails visibly before a network request', async () => {
    renderWithProviders(<NativeExperimentTracking />);
    fireEvent.change(screen.getByLabelText('Dataset manifest JSON: path and sha256'),{target:{value:'invalid-json'}});
    fireEvent.click(screen.getByRole('button',{name:'Prepare for review'}));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('malformed tracking data is an error rather than an empty successful list', async () => {
    vi.mocked(api.get).mockResolvedValue({});
    renderWithProviders(<NativeExperimentTracking />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid');
    expect(screen.queryByText('No runs in this project yet.')).not.toBeInTheDocument();
  });

  it('imports the actual selected zip bytes with the UI request header', async () => {
    runs = [{run_id:'rc-123456789abc',backend:'native',status:'ready_for_handoff',approvals:[{action:'release_bundle'}],metrics:{}}];
    const fetch = vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response('{"status":"failed"}',{status:200,headers:{'Content-Type':'application/json'}}));
    renderWithProviders(<NativeExperimentTracking />);
    const input = await screen.findByLabelText('Import results.zip');
    const file = new File(['controlled zip payload'], 'results.zip',{type:'application/zip'});
    fireEvent.change(input,{target:{files:[file]}});
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const [path, options] = fetch.mock.calls[0];
    expect(path).toBe('/api/compute/runs/rc-123456789abc/results');
    expect(options?.body).toBe(file);
    expect(new Headers(options?.headers).get('Content-Type')).toBe('application/zip');
    expect(new Headers(options?.headers).get('X-PhDLab-Client')).toBe('ui');
  });

  it('legacy coding history offers no launch, approval, cancel or session mutation', async () => {
    useUIStore.setState({activeTopicId:'topic-history'});
    vi.mocked(api.get).mockResolvedValue({sessions:[{id:'old-session',status:'running',payload:{spec:{goal:'old goal'}}}]});
    renderWithProviders(<OpenCodePanel />);
    expect(await screen.findByText('old-session: running')).toBeInTheDocument();
    expect(screen.getByText(/do not represent currently running processes/)).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });
});
