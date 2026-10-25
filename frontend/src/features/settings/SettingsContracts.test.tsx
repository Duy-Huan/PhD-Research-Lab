import React from 'react';
import { beforeEach,describe,expect,it,vi } from 'vitest';
import { fireEvent,screen,waitFor,within } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { api } from '../../shared/api/client';
import { useUIStore } from '../../shared/state/uiStore';
import { SettingsModal,applyFontById,applyThemeById } from './SettingsModal';

describe('settings persistence and provider isolation (explicit HTTP fixtures)',()=>{
  let config:any;
  beforeEach(()=>{
    vi.restoreAllMocks();localStorage.clear();applyThemeById('system');applyFontById('sans');
    useUIStore.setState({language:'en',settingsTab:'models',mainView:'settings'});
    config={version:'fixture',default_cloud:'openai',providers:{openai:{model:'openai-saved'},anthropic:{model:'anthropic-saved'}},
      provider_specs:{openai:{label:'OpenAI fixture',models:['openai-choice']},anthropic:{label:'Anthropic fixture',models:['anthropic-choice']}},
      agents:{assistant:{label:'Assistant fixture',default:'auto'}},agent_modes:{assistant:'auto'},agent_models:{},
      gateway:{cli_models:{codex:['codex-saved']}},local_model:'local-saved',ollama_model:'ollama-saved',
      mcp_agent:{models:['mcp-only']},runs:{slot_cpu:1,slot_cli:1,slot_cloud:2},ui:{language:'en'}};
    vi.spyOn(api,'get').mockImplementation(async url=>{
      if(url==='/api/config')return config;
      if(url==='/api/models/local')return {lmstudio:{models:['local-string',{id:'local-object'}]},ollama:{models:[{name:'ollama-object'}]}};
      if(url==='/api/models/connections')return {connections:[]};
      if(url.startsWith('/api/skills'))return {skills:[],errors:[]};
      if(url.startsWith('/api/plugins'))return {plugins:[],optional_plugins:[]};
      if(url.startsWith('/api/providers'))return {providers:[]};
      return {};
    });
    vi.spyOn(api,'post').mockImplementation(async(url,patch:any)=>url==='/api/config'?{...config,...patch}:{});
  });

  it.each([
    ['local',['local-saved','local-string','local-object'],'ollama-object'],
    ['ollama',['ollama-saved','ollama-object'],'local-object'],
    ['mcp',['mcp-only'],'openai-choice'],
    ['cloud',['openai-saved','openai-choice'],'anthropic-choice'],
    ['claude',['anthropic-saved','anthropic-choice'],'openai-choice'],
    ['codex',['codex-saved'],'openai-choice'],
  ])('keeps %s model options inside its provider scope',async(mode,allowed,forbidden)=>{
    config.agent_modes.assistant=mode;
    renderWithProviders(<SettingsModal />);
    const select=await screen.findByRole('combobox',{name:'assistant model'});
    await waitFor(()=>{for(const value of allowed)expect(within(select).getByRole('option',{name:value})).toBeInTheDocument();});
    expect(within(select).queryByRole('option',{name:forbidden})).not.toBeInTheDocument();
    fireEvent.change(select,{target:{value:allowed[0]}});
    await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/config',{agent_models:{assistant:allowed[0]}}));
  });

  it('selecting a provider resets the previous provider model before saving',async()=>{
    config.agent_models.assistant='old-foreign-model';renderWithProviders(<SettingsModal />);
    const select=await screen.findByRole('combobox',{name:'assistant provider'});
    fireEvent.change(select,{target:{value:'openai'}});
    await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/config',{
      agent_modes:{assistant:'openai'},agent_models:{assistant:'openai-saved'}}));
  });

  it.each([
    ['openscience-indigo','dark','#3b82f6'],['lab-midnight','dark','#a6b9ff'],['lab-forest','light','#27764b'],
  ])('applies and persists complete %s theme tokens', (id,base,accent)=>{
    applyThemeById(id);expect(document.documentElement.getAttribute('data-theme')).toBe(base);
    expect(document.documentElement.getAttribute('data-theme-package')).toBe(id);
    expect(document.documentElement.style.getPropertyValue('--accent')).toBe(accent);
    expect(localStorage.getItem('pl.theme')).toBe(id);
    applyThemeById('system');expect(document.documentElement.style.getPropertyValue('--accent')).toBe('');
    expect(document.documentElement.hasAttribute('data-theme-package')).toBe(false);
    expect(localStorage.getItem('pl.theme')).toBeNull();
  });

  it.each(['dark','light'])('plain %s theme clears custom tokens',id=>{
    applyThemeById('lab-forest');applyThemeById(id);
    expect(document.documentElement.getAttribute('data-theme')).toBe(id);
    expect(document.documentElement.style.getPropertyValue('--accent')).toBe('');
    expect(document.documentElement.hasAttribute('data-theme-package')).toBe(false);
  });

  it('font/theme still apply when browser storage quota is unavailable',()=>{
    vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new DOMException('quota','QuotaExceededError');});
    expect(()=>{applyThemeById('dark');applyFontById('serif');}).not.toThrow();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(document.documentElement.getAttribute('data-font')).toBe('serif');
    vi.spyOn(Storage.prototype,'removeItem').mockImplementation(()=>{throw new DOMException('denied','SecurityError');});
    expect(()=>{applyThemeById('system');applyFontById('sans');}).not.toThrow();
    expect(document.documentElement.hasAttribute('data-font')).toBe(false);
  });
});
