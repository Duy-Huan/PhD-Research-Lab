import React from 'react';
import { beforeEach,describe,expect,it,vi } from 'vitest';
import { fireEvent,screen,waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { api } from '../../shared/api/client';
import { useUIStore } from '../../shared/state/uiStore';
import { PaperOrchestraStudio } from './PaperOrchestraStudio';

// Explicit HTTP fixtures: these assert UI contracts, never scientific/provider execution.
describe('PaperOrchestraStudio workflow and evidence boundaries',()=>{
  beforeEach(()=>{
    vi.restoreAllMocks();useUIStore.setState({language:'en',activeTopicId:'topic-fixture'});
    vi.spyOn(window,'alert').mockImplementation(()=>{});
    vi.spyOn(api,'get').mockImplementation(async url=>url.endsWith('/health')
      ? {ready:true,detail:'Fixture engine status',cli:{installed:false}}
      : {artifacts:[]});
  });

  it('shows missing artifacts and refreshes only engine health',async()=>{
    renderWithProviders(<PaperOrchestraStudio />);
    expect(await screen.findByText('Fixture engine status')).toBeInTheDocument();
    expect(screen.getByText('(No artifacts recorded yet)')).toBeInTheDocument();
    expect(screen.getByText('Harness Skills Fallback')).toBeInTheDocument();
    fireEvent.click(screen.getByTitle('Refresh status'));
    await waitFor(()=>expect(vi.mocked(api.get).mock.calls.filter(([u])=>u.endsWith('/health'))).toHaveLength(2));
  });

  it('binds the selected section, objective and venue to the active topic mission',async()=>{
    const post=vi.spyOn(api,'post').mockResolvedValue({spec:{topic_id:'topic-fixture',tasks:[]}});
    renderWithProviders(<PaperOrchestraStudio />);
    await screen.findByText('Fixture engine status');
    fireEvent.click(screen.getByRole('button',{name:'L2'}));
    fireEvent.click(screen.getByRole('button',{name:'Introduction'}));
    const objective=screen.getByPlaceholderText(/Enter research objective/);
    fireEvent.change(objective,{target:{value:'  Compare measured baselines  '}});
    fireEvent.change(screen.getByDisplayValue('IEEE / ACM'),{target:{value:'IEEE TSE'}});
    fireEvent.click(screen.getByRole('button',{name:/L2 Writing Task/}));
    await waitFor(()=>expect(post).toHaveBeenCalledWith('/api/paperorchestra/plan-mission',{
      topic_id:'topic-fixture',level:'L2',objective:'Compare measured baselines',section:'introduction',target_venue:'IEEE TSE'}));
    expect(post).toHaveBeenCalledWith('/api/research/topics/topic-fixture/missions',{topic_id:'topic-fixture',tasks:[]});
  });

  it('surfaces a planning failure without claiming workflow success',async()=>{
    vi.spyOn(api,'post').mockRejectedValue(new Error('Workflow service unavailable'));
    renderWithProviders(<PaperOrchestraStudio />);await screen.findByText('Fixture engine status');
    fireEvent.click(screen.getByRole('button',{name:/L3 Writing Task/}));
    await waitFor(()=>expect(window.alert).toHaveBeenCalledWith('Error: Workflow service unavailable'));
    expect(vi.mocked(window.alert).mock.calls).toHaveLength(1);
  });

  it('cannot claim publication approval without a durable approval capability',async()=>{
    const post=vi.spyOn(api,'post');renderWithProviders(<PaperOrchestraStudio />);
    await screen.findByText('Fixture engine status');
    const sign=screen.getByRole('button',{name:'Sign-Off'});
    expect(sign).toBeDisabled();fireEvent.click(sign);
    expect(window.alert).not.toHaveBeenCalled();expect(post).not.toHaveBeenCalled();
  });

  it('requires an actual selected topic before creating a writing mission',async()=>{
    useUIStore.setState({activeTopicId:null});const post=vi.spyOn(api,'post');
    renderWithProviders(<PaperOrchestraStudio />);await screen.findByText('Fixture engine status');
    const launch=screen.getByRole('button',{name:/L3 Writing Task/});
    expect(launch).toBeDisabled();fireEvent.click(launch);expect(post).not.toHaveBeenCalled();
  });
});
