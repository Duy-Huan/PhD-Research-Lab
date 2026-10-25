# UI and UX audit

The [release report](RELEASE_READINESS.md) records selected Chromium 2D and actual WebGL2 3D results. Traces, screenshots, request/console logs and saved state are under the local run root. Desktop 1440×900 3D screenshots were visually inspected: the HPC scene rendered, the camera control was active and the chat dock opened. The test also returns to 2D.

Native forward labels now say **Open CLI App** and call the installed-app route. Provider status no longer defaults an unknown provider to ready. Chat/3D badge versions read the package version. The accessible label regression is repaired.

There is no approved pixel baseline for every panel, all six requested viewport classes, every hover/focus/keyboard interaction or every vendor terminal window. These remain UNVERIFIED. A passing scene test does not establish complete visual or accessibility coverage. Existing frontend build assets remain tracked because startup currently requires them; removing them needs a separately tested packaging change.
