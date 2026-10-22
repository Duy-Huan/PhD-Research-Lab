"""Windows child cleanup when taskkill is unavailable. Only descendants of our live Popen."""
import os


def stop_descendants(proc) -> None:
    if os.name != "nt" or proc.poll() is not None:
        return
    import ctypes as c
    from ctypes import wintypes as w

    class Entry(c.Structure):
        _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("pid", w.DWORD),
                    ("heap", c.c_size_t), ("module", w.DWORD), ("threads", w.DWORD),
                    ("parent", w.DWORD), ("priority", w.LONG), ("flags", w.DWORD), ("name", w.WCHAR * 260)]
    k = c.WinDLL("kernel32", use_last_error=True)
    k.GetProcessId.argtypes, k.GetProcessId.restype = [w.HANDLE], w.DWORD
    owned = getattr(proc, "_handle", None)
    if not isinstance(owned, int) or k.GetProcessId(owned) != proc.pid:
        return
    k.CreateToolhelp32Snapshot.argtypes, k.CreateToolhelp32Snapshot.restype = [w.DWORD, w.DWORD], w.HANDLE
    k.Process32FirstW.argtypes, k.Process32FirstW.restype = [w.HANDLE, c.POINTER(Entry)], w.BOOL
    k.Process32NextW.argtypes, k.Process32NextW.restype = [w.HANDLE, c.POINTER(Entry)], w.BOOL
    k.OpenProcess.argtypes, k.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    k.TerminateProcess.argtypes, k.TerminateProcess.restype = [w.HANDLE, w.UINT], w.BOOL
    k.WaitForSingleObject.argtypes, k.WaitForSingleObject.restype = [w.HANDLE, w.DWORD], w.DWORD
    k.CloseHandle.argtypes, k.CloseHandle.restype = [w.HANDLE], w.BOOL
    snapshot = k.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if snapshot in (None, c.c_void_p(-1).value):
        return
    parents = {}
    try:
        entry = Entry()
        entry.dwSize = c.sizeof(entry)
        more = k.Process32FirstW(snapshot, c.byref(entry))
        while more:
            parents[int(entry.pid)] = int(entry.parent)
            more = k.Process32NextW(snapshot, c.byref(entry))
    finally:
        k.CloseHandle(snapshot)
    # Walk a snapshot rooted at the process we own. Never target arbitrary matching executable names.
    descendants, frontier = [], [proc.pid]
    seen = {proc.pid}
    while frontier:
        parent = frontier.pop()
        for pid, ppid in parents.items():
            if ppid == parent and pid not in seen:
                seen.add(pid)
                descendants.append(pid)
                frontier.append(pid)
    for pid in reversed(descendants):
        handle = k.OpenProcess(0x100001, False, pid)  # SYNCHRONIZE | PROCESS_TERMINATE
        if handle:
            try:
                k.TerminateProcess(handle, 1)
                k.WaitForSingleObject(handle, 2000)
            finally:
                k.CloseHandle(handle)
