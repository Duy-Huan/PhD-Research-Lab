"""Best-effort Python/GIL stack snapshots, independent of test outcome/deadline enforcement.

Do not use faulthandler's native watchdog to walk live frames without the GIL.
CPython issues158200/140815 document native crashes in that path. Fatal-signal
handling stays enabled separately; the parent runner owns hard process deadlines.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import math
from pathlib import Path
import sys
import threading


def _snapshot() -> str:
    frames = sys._current_frames()
    frame = code = None
    lines = ['Python stack snapshot '+datetime.now(timezone.utc).isoformat()+'\n']
    try:
        for ident, frame in list(frames.items())[:100]:
            lines.append(f'Thread {ident:#x} (most recent call first):\n')
            for _ in range(100):
                if frame is None:
                    break
                code = frame.f_code
                lines.append(f'  File {ascii(code.co_filename[:500])}, line {frame.f_lineno}, in {code.co_name[:500]}\n')
                frame = frame.f_back
            if frame is not None:
                lines.append('  <remaining frames omitted: diagnostic bound>\n')
        if len(frames) > 100:
            lines.append('<remaining threads omitted: diagnostic bound>\n')
    finally:
        # Do not retain test frames, locals or the diagnostic thread's own cycle.
        frames.clear()
        frame = code = None
    text = ''.join(lines)
    return text[:1_000_000] + ('\n<snapshot truncated: diagnostic bound>\n' if len(text)>1_000_000 else '')


@contextmanager
def periodic_stacks(path: Path, interval_s: float = 300):
    """Yield the owned worker; always stop it without swallowing suite failures."""
    if type(interval_s) not in (int, float) or not math.isfinite(interval_s) or interval_s <= 0:
        raise ValueError('Diagnostic interval must be finite and positive')
    stopped = threading.Event()
    with Path(path).open('w', encoding='utf-8') as stream:
        def capture():
            while not stopped.wait(interval_s):
                try:
                    stream.write(_snapshot())
                    stream.flush()
                except (RuntimeError, OSError, ValueError) as error:
                    # A diagnostic failure is visible; it never becomes a test PASS.
                    print('Stack snapshot unavailable: '+type(error).__name__, file=sys.stderr)
        worker = threading.Thread(target=capture, name='verification-stack-snapshot', daemon=True)
        worker.start()
        try:
            yield worker
        finally:
            stopped.set()
            worker.join(timeout=5)
            if worker.is_alive():
                raise RuntimeError('Owned diagnostic worker did not stop')
