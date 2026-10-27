"""Operate the active paper project's independent Hermes runtime."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from backend.providers import hermes
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status', 'models', 'login', 'job'])
    parser.add_argument('--profile', choices=['review', 'assisted'], default='review')
    parser.add_argument('--job')
    args = parser.parse_args()
    if args.action == 'job': result = hermes.rpc('/v1/jobs/' + (args.job or ''), profile=args.profile)
    elif args.action == 'login':
        from backend.core.config import save_config
        save_config({'gateway': {'cli_profile': args.profile}})
        result = hermes.HermesConnector().connect(launch=True)
    elif args.action == 'models': result = hermes.refresh_models(args.profile)
    else: result = getattr(hermes, args.action)(args.profile)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__': main()
