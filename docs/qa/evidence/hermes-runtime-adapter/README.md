# Actual Hermes runtime development observations

Executed2026-10-26, on the exact uncommitted source fingerprints recorded in each receipt. These are scoped development observations, NOT whole-application QA/release qualification. Later source edits require fresh qualification.

- Official Nous sign-in completed by the owner; no token/password was returned through the backend.
- Actual account catalog424rows, eight with explicitly zero prompt/completion prices. The file contains catalog metadata, no credentials. Entitlement and successful inference are distinct.
- LIVE_PROVIDER: real existing gateway -> authenticated Docker HTTP/RPC -> official Python AIAgent, model stepfun/step-3.7-flash:free, returned exact nonce plus121. No fallback and no mock/model stub.
- LIVE_PROVIDER: fresh backend interpreter plus actual container stop/recreation, same project home retained. New prompt did not contain the nonce; the model recovered the exact nonce from persisted conversation history.
- LIVE_PROVIDER: adapter64e15b... called the actual native MCP research_get_current_state tool through Docker and a project-bound ephemeral read grant. It returned the random objective that was absent from its prompt; the native server audit confirms execution. Receipt native-tools-1792993917916754000.json is source-bound development evidence, not subsequent changed-source release qualification.
- REAL_CONTAINER_NETWORK: direct public HTTPS HEAD requests to Python.org, PyPI and GitHub returned200 in bridge mode. This earlier network receipt has adapter802d9e...; subsequent home-mount normalization did not execute this exact check again yet. Do not relabel it to the later adapter version.

No scientific result, learned skill improvement, complete native-tool integration, all-provider qualification, AI-UAT, production coverage or release readiness is inferred. Full software/real workflow validation remains pending after the requested feature-first implementation phase. Original UAT budgets are unchanged.
