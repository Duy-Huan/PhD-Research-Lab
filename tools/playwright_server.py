"""Run the actual application with disposable state for browser QA (no mocks)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--model", default="spark-x2.5-4b", help="Explicit installed LM Studio model; no fallback")
    parser.add_argument('--lease-token', default='', help='Owned disposable-server readiness nonce')
    parser.add_argument('--browser-uat',action='store_true',help='First-time persona: deny all writes except UI language; no CLI launches')
    args = parser.parse_args()
    data = args.data.resolve()
    artifact_root = (ROOT / "output" / "playwright").resolve()
    if not data.is_relative_to(artifact_root) or data == artifact_root:
        parser.error("Disposable state must be inside output/playwright/<run>/")
    data.mkdir(parents=True, exist_ok=True)
    os.environ["PHDLAB_DATA_DIR"] = str(data)
    os.environ["PHDLAB_URL"] = f"http://127.0.0.1:{args.port}"
    os.environ["JUPYTER_DATA_DIR"] = str(data / "_jupyter")
    from backend.core import config

    if not (data / "config.json").exists():
        config.save_config({
            "local_model": args.model,
            "lmstudio_base_url": "http://127.0.0.1:1234/v1",
            "agent_modes": {a: "local" for a in config.AGENTS},
            "agent_models": {a: args.model for a in config.AGENTS},
            "fallback_to_cloud": False,
            "research_os": {"enabled": True},
            "memory": {"embed_engine": "hashing", "auto_summarize": False},
            "lifecycle": {"unload_on_exit": False, "local_interactive": "keep_loaded"},
            "clearml": {"auto_record": False}, "ranking": {"auto": False},
            "ui": {"language": "en"},
        })
    import uvicorn
    from copy import deepcopy
    from backend.app import app

    if args.browser_uat:
        from fastapi.responses import JSONResponse
        from devtools.verification.uat import allowed_settings_write
        @app.middleware('http')
        async def scoped_browser_lease(request,call_next):
            if request.method not in ('GET','HEAD','OPTIONS'):
                try:body=await request.json()
                except ValueError:body=None
                if not allowed_settings_write(request.method,request.url.path,body):
                    return JSONResponse({'error':'Outside disposable settings-language UAT capability scope'},status_code=403)
            return await call_next(request)

    if args.lease_token:
        @app.get('/api/qa/lease', include_in_schema=False)
        def qa_lease():
            return {'nonce': args.lease_token, 'data': str(data)}

    logging_config = deepcopy(uvicorn.config.LOGGING_CONFIG)
    logging_config['handlers']['qa_file'] = {
        'class': 'logging.FileHandler', 'filename': str(data.parent / 'backend.log'),
        'formatter': 'default', 'encoding': 'utf-8',
    }
    for logger in logging_config['loggers'].values():
        logger['handlers'] = [*logger.get('handlers', []), 'qa_file']
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info",
                http="h11", loop="asyncio", ws="none", log_config=logging_config)


if __name__ == "__main__":
    main()
