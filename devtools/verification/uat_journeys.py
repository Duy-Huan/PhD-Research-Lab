"""Narrow disposable UAT capabilities and setup; never an application research engine."""
from __future__ import annotations
import base64
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import uuid

JOURNEYS = ('settings-language', 'project-and-chat', 'workflow-operations', 'failure-recovery')
CHAT_PROMPT = 'Return just the result of 13 plus 29. Do not use any tools.'
CHECKS = {
    'settings-language': {'language_vi_then_en', 'persisted_english', 'settings_visible'},
    'project-and-chat': {'owned_project_created', 'chat_request_observed', 'completed_local_turn',
                         'response_persisted', 'visible_after_reload', 'isolation_preserved'},
    'workflow-operations': {'initial_draft', 'approval_observed', 'review_observed', 'native_tasks_completed_once',
                            'native_raw_artifacts', 'zero_reasoning_calls', 'completed_visible'},
    'failure-recovery': {'exact_controlled_fault', 'reload_after_fault', 'successful_config_after_fault', 'settings_visible'},
}


def execution_key(journey: str, requested: str | None) -> str:
    if journey not in JOURNEYS:raise ValueError('Unsupported UAT journey')
    required='TASK-UAT-LOCAL-ADAPTER' if journey=='settings-language' else 'FQC-UAT-JOURNEYS-001'
    if requested not in (None,required) or (journey!='settings-language' and requested is None):
        raise ValueError('Use the existing contract-bound task identity; a new key cannot bypass the settings failure ledger')
    return required


def task(journey: str, lease: dict) -> str:
    if journey not in JOURNEYS:
        raise ValueError('Exploratory journey adapter is NOT_IMPLEMENTED: '+journey)
    if journey == 'settings-language':
        return ('Open System Settings. Use VI to switch to Vietnamese, then ENG to switch back to English. '
                'Finish while still on the Settings page.')
    if journey == 'project-and-chat':
        return (f"Use the Workspace menu to create a new project named exactly {lease['project_name']!r}. "
                'Leave custom folder fields empty. In the new project send this exact message: '+CHAT_PROMPT+
                ' Wait for the actual answer, reload the page, reopen that conversation and finish with its answer visible. '
                'Do not change provider/model, open tools or send another message.')
    if journey == 'workflow-operations':
        return (f"Select the prepared topic {lease['topic_title']!r} in the topic selector. Open Autonomous Missions, "
                'then Workflows L1–L4. Find the prepared Synthetic CPU UAT mission. Inspect Plan and results. '
                'Enter a Review note explicitly saying this is disposable synthetic UAT, not scientific approval. '
                'Approve plan and run. Wait for awaiting_review, inspect actual task results, then Complete review. '
                'Finish with completed visible. Do not create or edit other missions. '
                'L3 here names a harness interaction policy, not research-autonomy qualification.')
    return ('A single controlled GET /api/config HTTP503 fault is armed in this owned browser only. '
            'Reload once to encounter it, observe the actual error, then reload again to recover. '
            'Open System Settings and finish there. This tests controlled configuration-network recovery, '
            'not a real provider outage. Do not open providers, terminals or external sites.')


def allowed_write(journey: str, method: str, path: str, body: object, lease: dict) -> bool:
    """Default deny; IDs and paths come from owned setup, never from a model grant."""
    from .uat import allowed_settings_write
    if journey not in JOURNEYS or method != 'POST' or not isinstance(body, dict):
        return False
    if journey in ('settings-language', 'failure-recovery'):
        return allowed_settings_write(method, path, body)
    if journey == 'project-and-chat':
        if path == '/api/projects':
            return body == {'name': lease['project_name']} and not lease.get('project_created')
        if not lease.get('in_owned_project'):
            return False
        if path == '/api/chat/sessions':
            return (not lease.get('session_ids') and set(body) <= {'title', 'topic_id', 'chat_project', 'settings'}
                    and body.get('title') == CHAT_PROMPT[:48] and not body.get('topic_id')
                    and not body.get('chat_project') and body.get('settings', {}) == {})
        return (path in {f'/api/chat/sessions/{sid}/turns' for sid in lease.get('session_ids', [])}
                and not lease.get('turn_started') and set(body) <= {'text', 'overrides'}
                and body.get('text') == CHAT_PROMPT and body.get('overrides', {}) == {})
    base = f"/api/research/topics/{lease['topic_id']}/missions/{lease['mission_id']}"
    if path == base+'/approve':
        return (set(body) == {'plan_digest', 'note'} and body['plan_digest'] == lease['plan_digest']
                and isinstance(body['note'], str) and 1 <= len(body['note'].strip()) <= 4000)
    if path == base+'/review':
        return set(body) == {'note'} and isinstance(body['note'], str) and 1 <= len(body['note'].strip()) <= 4000
    return False


def prepare(journey: str, data: Path, model: str) -> dict:
    """Deterministic synthetic setup only; no inference, fabricated run or scientific review."""
    if journey not in JOURNEYS:
        raise ValueError('Unsupported UAT journey')
    from backend.core import config
    config.save_config({'aiws': {'provider': 'app:local', 'model': model, 'mcp_auto': False, 'mcp_tools': ['-'],
        'memory_mode': 'off', 'context_mode': 'none', 'summaries': False, 'collect_artifacts': False,
        'keep_history': True, 'auto_memory_types': [], 'module_defaults': {}}})
    lease = {'journey': journey, 'data_root': str(data.resolve()), 'model': model,
             'setup_mode': 'DETERMINISTIC_SYNTHETIC_FIXTURE', 'scientific_review': 'PENDING'}
    if journey == 'project-and-chat':
        from backend.agent import sessions
        sentinel = sessions.create('UAT default-project isolation marker', 'global', '', '', {})
        lease.update(project_name='UAT project '+uuid.uuid4().hex[:10], sentinel_id=sentinel['id'])
    elif journey == 'workflow-operations':
        from backend.knowledge import research_store as store
        from backend.execution import protocols
        from backend.execution.protocol_contracts import ExperimentProtocol
        from backend.agent import missions
        from backend.agent.mission_contracts import MissionSpec
        topic = store.save_topic(store.TopicInput(title='UAT synthetic CPU topic '+uuid.uuid4().hex[:8]))
        protocol = protocols.create(ExperimentProtocol(topic_id=topic['id'], hypothesis='Synthetic CPU UAT fixture; no empirical scientific claim',
            dataset={'side': 8, 'train_count': 1, 'validation_count': 1, 'test_count': 1},
            seeds=[11], alphas=[0.5], max_trials=4, max_seconds=15, max_artifact_mb=2))
        approved = protocols.approve(topic['id'], protocol['id'], protocol['digest'],
            'Deterministic disposable synthetic UAT fixture authorization; not independent or scientific review')
        mission = missions.create(MissionSpec.model_validate({'topic_id': topic['id'], 'objective': 'Synthetic CPU UAT mission',
            'permissions': ['compute', 'workspace_write'], 'limits': {'max_seconds': 30, 'max_reasoning_calls': 0,
                'max_attempts': 1, 'max_artifact_mb': 2}, 'autonomy': {'level': 'L3'},
            'control': {'success_criteria': ['Owned CPU artifacts and report are retained'], 'allowed_engines': ['deterministic'],
                'allow_api_billing': False, 'end_date': (datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(),
                'max_wall_seconds': 60, 'review_required': True},
            'tasks': [{'id': 'experiment', 'capability': 'experiment.run', 'args': {'protocol_id': approved['id'],
                'protocol_digest': approved['digest'], 'approval_nonce': approved['approval']['nonce']}},
                {'id': 'report', 'capability': 'mission.report', 'depends_on': ['experiment']}]}))
        lease.update(topic_id=topic['id'], topic_title=topic['title'], protocol_id=approved['id'],
                     mission_id=mission['id'], plan_digest=mission['payload']['plan_digest'], initial_mission=mission)
    return lease


def snapshot(lease: dict) -> dict:
    """Read actual owned state/bytes. Its existence alone never means acceptance passed."""
    from backend.core import config
    result = {'lease': lease, 'project': config.active_project()}
    root = Path(lease['data_root']).resolve()
    if not config.data_dir().resolve().is_relative_to(root):
        raise ValueError('UAT active project escaped its data root')
    if lease['journey'] == 'project-and-chat':
        from backend.agent import sessions
        result['sessions'] = [sessions.get(s['id']) for s in sessions.list_sessions()]
        result['in_owned_project'] = (config.data_dir().resolve().is_relative_to(root/'projects')
            and result['project']['name'] == lease['project_name'])
    elif lease['journey'] == 'workflow-operations':
        from backend.agent import missions
        from backend.execution import protocols
        mission = missions.get(lease['mission_id'], lease['topic_id'])
        result.update(mission=mission, runs=protocols.runs(lease['topic_id']), raw_artifacts=[])
        refs = [trial['payload'].get('artifact', {}) for run in result['runs'] for trial in run['trials']]
        refs += [ref for task in mission['tasks'] for ref in task['payload'].get('result', {}).get('artifacts', [])]
        for ref in refs:
            path = Path(ref.get('path', '')).resolve()
            if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > 2_000_000:
                raise ValueError('Missing, oversized or unowned native UAT artifact')
            raw = path.read_bytes();digest = hashlib.sha256(raw).hexdigest()
            if digest != ref.get('sha256') or len(raw) != ref.get('bytes'):
                raise ValueError('Changed native UAT artifact')
            result['raw_artifacts'].append({'path': path.relative_to(root).as_posix(), 'sha256': digest,
                'bytes': len(raw), 'content_base64': base64.b64encode(raw).decode()})
    return result
