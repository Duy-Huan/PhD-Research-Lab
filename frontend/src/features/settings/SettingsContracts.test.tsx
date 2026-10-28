import React from 'react';
import { beforeEach,describe,expect,it,vi } from 'vitest';
import { fireEvent,screen,waitFor,within } from '@testing-library/react';
import { renderWithProviders } from '../../test/test-utils';
import { api } from '../../shared/api/client';
import { useUIStore } from '../../shared/state/uiStore';
import { SettingsModal,applyFontById,applyThemeById,restoreSavedTheme } from './SettingsModal';

describe('saved theme on start (FQC-CLI-STUDIO-663 QA finding)',()=>{
  it('applies the theme the researcher chose before the first render after a reload',()=>{
    applyThemeById('lab-midnight');
    document.documentElement.removeAttribute('data-theme');document.documentElement.removeAttribute('data-theme-package');
    document.documentElement.style.removeProperty('--accent');
    restoreSavedTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme-package')).toBe('lab-midnight');
    applyThemeById('system');document.documentElement.removeAttribute('data-theme');
    restoreSavedTheme();
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
  });
});

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
      if(url==='/api/models') {
        const canonical: Record<string,string> = {local:'app:local',ollama:'app:ollama',mcp:'mcp',cloud:'app:openai',claude:'app:anthropic',codex:'cli:codex',auto:'app:auto'};
        return {agent_catalog:{assistant:{provider_id:canonical[config.agent_modes.assistant] || config.agent_modes.assistant}},providers:[
          {id:'app:auto',label:'Auto fixture',models:[]},
          {id:'app:openai',label:'OpenAI fixture',models:['openai-saved','openai-choice']},
          {id:'app:anthropic',label:'Anthropic fixture',models:['anthropic-saved','anthropic-choice']},
          {id:'cli:codex',label:'Codex subscription fixture',models:['codex-saved']},
        ]};
      }
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

  it('shows the CLI connections with the Claude long-lived token in the models tab (was imported but never rendered)',async()=>{
    const get=api.get as any;const fixture=get.getMockImplementation();
    get.mockImplementation(async(url:string)=>url==='/api/models'?{agent_catalog:{assistant:{provider_id:'app:auto'}},providers:[
      {id:'cli:claude_code',label:'Claude (Claude Code CLI)',transport:'cli',state:'CONNECTED',available:true,models:[],readiness:{}}]}:fixture(url));
    renderWithProviders(<SettingsModal />);
    const region=await screen.findByRole('region',{name:'Unified AI connections'});
    expect(await within(region).findByLabelText(/Long-lived Claude token/)).toBeInTheDocument();
  });

  it('leaves the source-code firewall off unless the researcher turned it on',async()=>{
    useUIStore.setState({settingsTab:'mcp'});
    const view=renderWithProviders(<SettingsModal />);
    const firewall=await screen.findByRole('checkbox',{name:/Context Firewall/});
    expect(firewall).not.toBeChecked();
    fireEvent.click(firewall);
    await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/config',{gateway:{block_source_code:true}}));
    view.unmount();config.gateway.block_source_code=true;
    renderWithProviders(<SettingsModal />);
    expect(await screen.findByRole('checkbox',{name:/Context Firewall/})).toBeChecked();
  });

  it('selecting a provider resets the previous provider model before saving',async()=>{
    config.agent_models.assistant='old-foreign-model';renderWithProviders(<SettingsModal />);
    const select=await screen.findByRole('combobox',{name:'assistant provider'});
    fireEvent.change(select,{target:{value:'app:openai'}});
    await waitFor(()=>expect(api.post).toHaveBeenCalledWith('/api/config',{
      agent_modes:{assistant:'app:openai'},agent_models:{assistant:'openai-saved'}}));
  });

  it.each([
    ['research-indigo','dark','#3b82f6'],['lab-midnight','dark','#a6b9ff'],['lab-forest','light','#27764b'],
  ])('applies and persists complete %s theme tokens', (id,base,accent)=>{
    applyThemeById(id);expect(document.documentElement.getAttribute('data-theme')).toBe(base);
    expect(document.documentElement.getAttribute('data-theme-package')).toBe(id);
    expect(document.documentElement.style.getPropertyValue('--accent')).toBe(accent);
    expect(localStorage.getItem('pl.theme')).toBe(id);
    applyThemeById('system');expect(document.documentElement.style.getPropertyValue('--accent')).toBe('');
    expect(document.documentElement.hasAttribute('data-theme-package')).toBe(false);
    expect(localStorage.getItem('pl.theme')).toBeNull();
  });

  it('migrates the retired saved theme without losing appearance',()=>{
    applyThemeById('openscience-indigo');
    expect(document.documentElement.getAttribute('data-theme-package')).toBe('research-indigo');
    expect(document.documentElement.style.getPropertyValue('--accent')).toBe('#3b82f6');
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
