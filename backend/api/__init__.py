"""HTTP API of PhD Research Lab (one backend for the browser UI and the `phdlab` CLI).

    system     version, settings, models (picker, local engines, unload), research providers, dashboard, event bus
    projects   research projects, the research outline (levels + attached proposal), project files
    chat       conversations, turns ("/" skills), live events, Accept / Reject, attachments, artifacts, skills
    runs       background research runs (state, timeline, approve / cancel / resume / swap provider), acceptance
    memory     memory proposals, research state (read-only), pinned results
    code       code projects, VS Code, results back from VS Code, experiment jobs
    library    PDFs, metadata, BibTeX
    paper      sections, LaTeX → PDF, export
    review     the paper review session
    mcp        MCP research tools for CLI providers
    plugins    GitHub skill plugins, automatic venue ranking, AI-Scientist-v2 manuscript writer, document export
"""
from backend.api import chat, code, compute, library, mcp, memory, paper, plugins, projects, research_engines, review, runs, system

ROUTERS = [system.router, projects.router, chat.router, runs.router, memory.router, code.router, library.router,
           paper.router, review.router, mcp.router, plugins.router, compute.router, research_engines.router]
