"""Optional local-only Browser Use adapter. No personal profile, files or cloud key."""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
import sys
import traceback


def restrict_worker(out: Path, ports: set[int]) -> list[dict]:
    """Defense in depth for Python actions; browser request egress has its own proxy."""
    denied=[]; writable=out.resolve();readable=[Path(sys.prefix).resolve(),Path(sys.base_prefix).resolve(),writable]
    def audit(event,args):
        reason=None
        if event=='open' and args and not isinstance(args[0],int):
            path=Path(args[0]).resolve()
            writing=any(c in (args[1] or '') for c in 'wax+') or bool(args[2]& (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
            if not any(path.is_relative_to(p) for p in readable) or (writing and not path.is_relative_to(writable)):
                reason='File access outside isolated adapter workspace/runtime'
        elif event in ('os.listdir','os.scandir') and args and args[0] is not None and not isinstance(args[0],int):
            path=Path(args[0]).resolve()
            if not any(path.is_relative_to(p) for p in readable):reason='Directory access outside isolated adapter runtime'
        elif event in ('os.remove','os.rmdir','os.mkdir','os.truncate','os.chmod','os.utime'):
            if args and (isinstance(args[0],int) or not Path(args[0]).resolve().is_relative_to(writable)):
                reason='Filesystem mutation outside isolated adapter workspace'
        elif event in ('os.rename','os.link','os.symlink'):
            if any(not Path(value).resolve().is_relative_to(writable) for value in args[:2]):
                reason='Filesystem move/link outside isolated adapter workspace'
        elif event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn'):
            reason='Subprocess actions are disabled in the browser AI worker'
        elif event=='socket.connect':
            address=args[1]
            if isinstance(address,tuple) and (address[0] not in ('127.0.0.1','::1','localhost') or address[1] not in ports):
                reason='Network target outside owned browser/app/local-model allowlist'
        if reason:
            denied.append({'event':event,'reason':reason});raise PermissionError(reason)
    sys.addaudithook(audit)
    return denied


async def execute(options: dict) -> dict:
    os.environ.update(ANONYMIZED_TELEMETRY='false', DO_NOT_TRACK='1', BROWSER_USE_CLOUD_SYNC='false', BROWSER_USE_LOGGING_LEVEL='error')
    out=Path(options['out']);lease=json.loads((out/'browser-lease.json').read_text(encoding='utf-8'))
    from urllib.parse import urlsplit
    cdp=urlsplit(lease['cdp_url'])
    if cdp.scheme!='http' or cdp.hostname!='127.0.0.1' or not cdp.port or lease.get('personal_profile') is not False:
        raise ValueError('Browser Use requires an owned loopback CDP lease')
    denied=restrict_worker(out,{cdp.port,urlsplit(lease['app_origin']).port,1234})
    from browser_use import Agent, Browser, ChatOpenAI, Tools
    from importlib.metadata import version
    safe={'navigate','click','input','scroll','wait','go_back','dropdown_options','select_dropdown',
          'send_keys','switch','find_elements','find_text','search_page','screenshot','done'}
    known=set(Tools().registry.registry.actions)
    tools=Tools(exclude_actions=sorted(known-safe))
    browser=Browser(cdp_url=lease['cdp_url'],is_local=False,use_cloud=False,allowed_domains=[lease['app_origin']],
                    keep_alive=True,enable_default_extensions=False,permissions=[],accept_downloads=False)
    llm=ChatOpenAI(model=options['model'],base_url='http://127.0.0.1:1234/v1',api_key='local-uat-only',
                   max_retries=0,timeout=45,max_completion_tokens=6000,frequency_penalty=None,reasoning_effort=None)
    task=(f"Test the disposable app at {lease['app_origin']}/dist/react.html. "
          "Open System Settings. Use its VI button to switch to Vietnamese, then its ENG button to switch back to English. "
          "Finish while still on the Settings page. Observe loading, layout and errors. "
          "Only interact with this local test app. Do not open providers, terminals, file pickers or external sites. "
          "Report actual observations and exact actions. Do not invent a UX score, a pass, or measurements.")
    async def stop_after_three_errors():
        return sum(bool(error) for error in agent.history.errors()) >= 3
    agent=Agent(task=task,llm=llm,browser=browser,tools=tools,use_vision=False,use_judge=False,
                calculate_cost=False,available_file_paths=[],file_system_path=str(out/'agent-workspace'),
                save_conversation_path=out/'conversation',max_failures=3,max_actions_per_step=2,
                max_history_items=6,max_clickable_elements_length=8000,use_thinking=False,
                enable_planning=False,final_response_after_failure=False,llm_timeout=45,step_timeout=60,
                message_compaction=False,register_should_stop_callback=stop_after_three_errors)
    try:
        history=await asyncio.wait_for(agent.run(max_steps=options['max_steps']),timeout=options['timeout_s'])
        history.save_to_file(str(out/'agent-history.json'))
        return {'adapter_available':True,'adapter':'browser-use','version':version('browser-use'),
                'model_requested':options['model'],'model_returned':'UNKNOWN',
                'max_completion_tokens':6000,
                'mode':'REAL_LOCAL','ai_success':history.is_successful() is True,'steps':len(history.history),
                'urls':history.urls(),'actions':history.model_actions(),'errors':history.errors(),
                'observations':history.final_result(),'vision':'DOM_ONLY',
                'blocked_worker_actions':denied,
                'limitations':['AI observations are UNCONFIRMED until deterministic reproduction',
                               'This adapter does not provide independent acceptance review']}
    finally:
        if not (out/'agent-history.json').exists():
            agent.history.save_to_file(str(out/'agent-history.json'))
        await browser.stop()


def main() -> int:
    options=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));out=Path(options['out'])
    try:record=asyncio.run(execute(options))
    except Exception as exc:
        record={'adapter_available':True,'mode':'REAL_LOCAL','status':'BLOCKED','ai_success':False,
                'error':type(exc).__name__+': '+str(exc)[:2000],'traceback':traceback.format_exc()}
    (out/'agent-result.json').write_text(json.dumps(record,indent=2,default=str)+'\n',encoding='utf-8')
    return 0 if record.get('ai_success') else 2


if __name__=='__main__':raise SystemExit(main())
