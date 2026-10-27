"""Stop a process we own and the processes it started, on Windows without psutil or taskkill.

Windows reuses PIDs and never re-parents orphans, so "ParentProcessId == X" also matches long-lived processes whose
real parent died long ago and whose PID was later reused by our child. taskkill /T and a plain snapshot walk then kill
unrelated processes (in CI this took down the GitHub runner itself: no log, no artifact, job killed at its limit).
A process is accepted as a descendant only if it was created no earlier than the parent it names, and it is
terminated through the same handle that was checked, so its PID cannot be reused between the check and the kill.
"""
import os
from typing import Callable


def select_descendants(root: int, root_created: int, parents: dict[int, int],
                       created: Callable[[int], int | None]) -> list[int]:
    """Descendants of root, parents before children. created(pid) is None when the process is gone or unreadable."""
    found, frontier, seen = [], [(root, root_created)], {root}
    while frontier:
        parent, parent_created = frontier.pop(0)
        for pid, ppid in sorted(parents.items()):
            if ppid != parent or pid in seen:
                continue
            when = created(pid)
            if when is None or when < parent_created:
                continue  # stale parent link: this process is older than the parent PID it reports
            seen.add(pid)
            found.append(pid)
            frontier.append((pid, when))
    return found


def stop_tree(proc) -> None:
    """Terminate an owned Popen and its true descendants (Windows); elsewhere only the owned process."""
    if proc.poll() is not None:
        return
    if os.name != "nt":
        proc.kill()
        return
    import ctypes as c
    from ctypes import wintypes as w

    class Entry(c.Structure):
        _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("pid", w.DWORD),
                    ("heap", c.c_size_t), ("module", w.DWORD), ("threads", w.DWORD),
                    ("parent", w.DWORD), ("priority", w.LONG), ("flags", w.DWORD), ("name", w.WCHAR * 260)]
    k = c.WinDLL("kernel32", use_last_error=True)
    k.GetProcessId.argtypes, k.GetProcessId.restype = [w.HANDLE], w.DWORD
    k.CreateToolhelp32Snapshot.argtypes, k.CreateToolhelp32Snapshot.restype = [w.DWORD, w.DWORD], w.HANDLE
    k.Process32FirstW.argtypes, k.Process32FirstW.restype = [w.HANDLE, c.POINTER(Entry)], w.BOOL
    k.Process32NextW.argtypes, k.Process32NextW.restype = [w.HANDLE, c.POINTER(Entry)], w.BOOL
    k.OpenProcess.argtypes, k.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    k.GetProcessTimes.argtypes, k.GetProcessTimes.restype = [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4, w.BOOL
    k.TerminateProcess.argtypes, k.TerminateProcess.restype = [w.HANDLE, w.UINT], w.BOOL
    k.WaitForSingleObject.argtypes, k.WaitForSingleObject.restype = [w.HANDLE, w.DWORD], w.DWORD
    k.CloseHandle.argtypes, k.CloseHandle.restype = [w.HANDLE], w.BOOL

    def created_at(handle) -> int | None:
        times = [w.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle, *[c.byref(t) for t in times]):
            return None
        return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime

    owned = getattr(proc, "_handle", None)
    root_created = created_at(owned) if isinstance(owned, int) and k.GetProcessId(owned) == proc.pid else None
    handles: dict[int, int] = {}
    try:
        if root_created is not None:
            parents: dict[int, int] = {}
            snapshot = k.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
            if snapshot not in (None, c.c_void_p(-1).value):
                try:
                    entry = Entry()
                    entry.dwSize = c.sizeof(entry)
                    more = k.Process32FirstW(snapshot, c.byref(entry))
                    while more:
                        parents[int(entry.pid)] = int(entry.parent)
                        more = k.Process32NextW(snapshot, c.byref(entry))
                finally:
                    k.CloseHandle(snapshot)

            def created(pid: int) -> int | None:
                handle = handles.get(pid) or k.OpenProcess(0x101001, False, pid)  # SYNCHRONIZE|QUERY_LIMITED|TERMINATE
                if not handle:
                    return None
                handles[pid] = handle
                return created_at(handle)

            for pid in reversed(select_descendants(proc.pid, root_created, parents, created)):
                k.TerminateProcess(handles[pid], 1)
                k.WaitForSingleObject(handles[pid], 2000)
    finally:
        for handle in handles.values():
            k.CloseHandle(handle)
    if proc.poll() is None:
        proc.kill()  # the owned process itself, through Popen's own handle
