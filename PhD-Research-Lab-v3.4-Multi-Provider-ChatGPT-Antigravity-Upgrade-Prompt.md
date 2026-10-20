# PhD Research Lab v3.3 → v3.4
# Multi-Provider Subscription Integration Upgrade
## ChatGPT + Google Antigravity + Local Context Gateway

> **Milestone objective:** Upgrade PhD Research Lab into a provider-agnostic local research backend. ChatGPT and Google Antigravity should consume the same local Context Memory, Research State, Evidence and tools. Claude Code must remain compatible with the same backend.
>
> **Primary integrations:** ChatGPT through an officially supported authorization/integration path where eligible, and Google Antigravity through supported MCP. Do **not** reverse-engineer or scrape consumer chat websites.

---

## 0. NON-NEGOTIABLE POLICY & SECURITY RULE

Never implement:

- browser cookie/session extraction
- private/undocumented provider endpoints
- DOM scraping intended to turn a consumer chat site into an unofficial API
- fake client/user-agent impersonation
- quota circumvention
- account/IP rotation to bypass limits
- automatic API fallback that silently creates billing
- plaintext storage of provider credentials

Use only:

- official SDKs/APIs
- officially supported OAuth/sign-in mechanisms
- supported MCP
- first-party clients such as Claude Code / Google Antigravity
- explicit user authorization

If a desired integration cannot be implemented through an officially supported mechanism, document the limitation instead of inventing a workaround.

---

# 1. FIRST TASK — AUDIT v3.3

Before modifying code:

1. Inspect the complete repository.
2. Read existing backend/context-memory documentation.
3. Map:
   - backend
   - Context Memory
   - Context Compiler
   - Retrieval
   - MCP
   - agents
   - provider adapters
   - authentication
   - secrets
   - SSE/WebSocket
   - workers
   - persistence
   - tests
4. Run the complete test suite.
5. Record baseline performance.
6. Identify existing Claude Code integration.
7. Determine whether MCP already exists.

Create/update:

```text
docs/architecture/multi-provider-v3.4-audit.md
```

Do not perform a blind rewrite.

---

# 2. TARGET ARCHITECTURE

Build toward:

```text
                         USER
                          │
                          ▼
                ┌────────────────────┐
                │ PhD Research Lab   │
                │ Local Backend      │
                └─────────┬──────────┘
                          │
                  Provider Gateway
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
     ChatGPT         Claude Code      Antigravity
     official        first-party       MCP client
         │                │                │
         └────────────────┼────────────────┘
                          ▼
                ┌────────────────────┐
                │ Local MCP Gateway │
                └─────────┬──────────┘
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
 Context Gateway     Research State      Tool Gateway
       │                  │                  │
       ▼                  ▼                  ▼
 Memory Engine       Evidence/          Sandbox/Docker
                     Provenance          ClearML/Git
                          │
                          ▼
                     Local Storage
```

Keep it modular and local-first. Do not introduce microservices unless profiling proves they are necessary.

---

# 3. PROVIDER-AGNOSTIC CORE

Create/improve a common provider abstraction:

```python
class ProviderConnector:
    provider_id: str

    def capabilities(self): ...
    def health(self): ...
    def start_session(self, context): ...
    def send_message(self, message, context): ...
    def stream_message(self, message, context): ...
    def cancel(self, request_id): ...
```

Adapt this to the repository's existing architecture.

Provider-specific code must not leak into:

- Context Memory
- Research State
- Evidence
- experiments
- UI
- agent business logic

---

# 4. CHATGPT INTEGRATION

## Goal

Integrate ChatGPT through an officially supported authentication mechanism for eligible applications/accounts.

Preferred flow:

```text
PhD-Lab
  ↓
Connect ChatGPT
  ↓
Official authorization flow
  ↓
User authenticates in browser
  ↓
Permission granted
  ↓
Secure local credential/session storage
  ↓
ChatGPT Provider Connector
  ↓
Context Gateway
```

Requirements:

- never collect the user's password
- never copy browser cookies
- never store raw credentials
- support disconnect/revoke
- expose connection state
- handle authorization expiry
- do not assume quota information is available

If supported, normalize streaming into the local event system.

Do not use private ChatGPT endpoints.

---

# 5. GOOGLE ANTIGRAVITY INTEGRATION

Use Antigravity as a first-party AI environment and connect it to PhD-Lab through supported MCP.

Expose research-oriented tools such as:

```text
research.get_current_state
research.search_memory
research.get_hypothesis
research.get_experiment
research.get_evidence
research.get_decisions
research.get_failures
research.get_context
research.record_observation
research.record_decision
research.record_experiment_result
```

Do not expose raw database/filesystem access unless required.

Do not attempt to turn Antigravity's subscription into a generic unofficial API.

---

# 6. MCP TOOL DESIGN

Prefer semantic research tools:

```text
research.search_memory
research.get_current_state
research.get_relevant_evidence
research.get_experiment
research.get_failure_history
research.get_hypothesis
research.get_context_packet
research.record_decision
research.record_experiment_result
```

Avoid exposing:

```text
read_sql
query_database
read_any_file
```

unless they are strictly sandboxed.

Every MCP tool needs:

- strict schema
- input validation
- minimal permissions
- structured output
- error handling
- provenance

---

# 7. SHARED CONTEXT MEMORY

Do **not** create separate memories:

```text
ChatGPT Memory
Claude Memory
Gemini Memory
```

Instead:

```text
                    Local Research Memory
                           │
           ┌───────────────┼───────────────┐
           ↓               ↓               ↓
        ChatGPT        Claude Code     Antigravity
```

The local backend is the source of truth.

---

# 8. CONTEXT GATEWAY

Implement:

```text
Provider Request
      ↓
Context Gateway
      ↓
Research State
      ↓
Hybrid Retrieval
      ↓
Evidence Selection
      ↓
Context Compiler
      ↓
Provider Adapter
      ↓
Provider
```

Retrieval context should consider:

```text
query
project
research objective
active hypothesis
active experiment
agent role
recent decisions
known failures
constraints
dataset
model
hardware
relevant papers
evidence
token budget
```

---

# 9. CANONICAL RESEARCH CONTEXT

Create a provider-independent internal context packet:

```json
{
  "schema_version": "1.0",
  "project_id": "...",
  "objective": "...",
  "active_hypothesis": "...",
  "active_experiment": "...",
  "constraints": [],
  "recent_decisions": [],
  "relevant_evidence": [],
  "known_failures": [],
  "artifacts": [],
  "provenance": [],
  "retrieval_trace": {}
}
```

Do not blindly send the complete packet to the model. The Context Compiler decides what is exposed.

---

# 10. ROLE-AWARE CONTEXT COMPILATION

Use different policies for:

```text
Literature Agent
Experiment Designer
Coding Agent
Paper Writer
Paper Reviewer
Research Director
```

The compiler should optimize:

```text
relevance
+
evidence quality
+
research-state fit
+
recency
+
task fit
+
token budget
-
redundancy
-
low-confidence information
```

---

# 11. PRIVACY / SENSITIVITY FILTER

Classify research information:

```text
PUBLIC
INTERNAL
SENSITIVE
RESTRICTED
```

Default:

```text
PUBLIC       → allowed
INTERNAL     → project policy / optional confirmation
SENSITIVE    → blocked by default
RESTRICTED   → blocked
```

Add a project policy such as:

```text
"Never send proprietary source code to external models."
```

Enforce this **before** provider requests.

---

# 12. HUMAN-IN-THE-LOOP EXTERNAL CONTEXT REVIEW

Add an optional:

```text
Review before external AI
```

mode.

Example:

```text
Provider: ChatGPT
Context: 14.2k tokens

Includes:
✓ hypothesis
✓ experiments
✓ papers
✓ metrics
✓ failures

Blocked:
✗ restricted files
✗ private source code

[Send] [Edit] [Cancel]
```

This is especially important for research related to sensitive/company information.

---

# 13. MEMORY WRITE-BACK

Never automatically turn provider output into permanent memory.

Use:

```text
Provider output
      ↓
Candidate extraction
      ↓
Classification
      ↓
Evidence/provenance check
      ↓
User approval or policy
      ↓
Memory write
```

Distinguish:

```text
AI suggestion
AI claim
verified observation
experiment result
human decision
validated evidence
```

---

# 14. STREAMING

Normalize provider streams:

```text
Provider
   ↓
ProviderEvent
   ↓
EventNormalizer
   ↓
InternalEvent
   ↓
SSE/WebSocket
   ↓
UI
```

Support:

```text
request_started
text_delta
tool_call
tool_result
status
error
request_completed
request_cancelled
```

Never couple the UI directly to a provider's event format.

---

# 15. MULTI-PROVIDER SESSION

Support:

```text
Session
 ├── ChatGPT
 ├── Claude
 └── Antigravity
```

A user can explicitly choose:

```text
Ask ChatGPT
Ask Claude
Ask Antigravity
Compare answers
```

Comparison mode:

```text
Question
   ↓
same canonical research context
   ├── ChatGPT
   ├── Claude
   └── Antigravity
   ↓
responses
   ↓
user/local evaluator
```

Do not automatically send one provider's response to another unless explicitly enabled.

---

# 16. PROVIDER HEALTH / FALLBACK

Use explicit states:

```text
CONNECTED
DISCONNECTED
AUTH_EXPIRED
RATE_LIMITED
UNAVAILABLE
ERROR
UNKNOWN
```

Never silently fall back to a paid API.

Example:

```text
ChatGPT unavailable
↓
"ChatGPT unavailable. Use Claude / Antigravity?"
```

---

# 17. COST GUARD

Default configuration:

```text
ChatGPT:
Subscription integration: ON
API fallback: OFF

Claude:
Claude Code: ON
API fallback: OFF

Antigravity:
Subscription/first-party path: ON
API fallback: OFF
```

The backend must clearly show which provider/path is being used.

Never create or activate API billing automatically.

---

# 18. SECURITY

Implement:

```text
local-only default binding
authentication for remote MCP
origin validation
request validation
rate limiting
audit logs
secret redaction
safe subprocess handling
path traversal protection
```

Bind locally by default:

```text
127.0.0.1
```

Do not expose the research backend publicly unless explicitly configured.

Never log:

```text
password
OAuth secret
refresh token
API key
private credential
restricted raw document
```

---

# 19. PERFORMANCE

Measure:

```text
MCP tool latency
Context retrieval latency
Context compilation latency
authentication overhead
stream startup latency
first-token latency
memory write latency
database latency
cache hit rate
```

Suggested targets:

```text
local memory lookup: <100 ms
context retrieval: <500 ms where practical
context compilation: <300 ms excluding provider latency
simple MCP tool: <200 ms where practical
```

Do not trade research correctness for speed.

---

# 20. CACHE

Cache where profiling justifies it:

```text
research state
embeddings
retrieval results
context packets
MCP metadata
```

Invalidate on:

```text
new experiment
new decision
new evidence
memory update
project change
```

Avoid stale research state.

---

# 21. OBSERVABILITY

Every provider request should record:

```text
request_id
provider
session_id
project_id
agent_id
context_version
context_tokens
retrieval_count
latency
streaming
cache_hit
error
```

Never log credentials or restricted content.

Add optional Context Trace:

```text
CONTEXT TRACE

Task:
Design denoising experiment

Research state:
HYPE-007

Retrieved:
EXP-013  score=0.91
FAIL-003 score=0.87
PAPER-022 score=0.83

Dropped:
CHAT-192 low relevance
PAPER-011 duplicate

Compiled:
Research: 8.2k
Evidence: 3.1k
Knowledge: 2.7k
Working: 1.9k

Total: 15.9k tokens
```

---

# 22. TESTING

Add:

```text
tests/providers/
tests/mcp/
tests/context_gateway/
tests/streaming/
tests/security/
tests/integration/
```

Test:

### ChatGPT

- authorization abstraction
- connection state
- disconnect
- streaming normalization
- provider errors
- authorization expiry
- no automatic API fallback

### Antigravity

- MCP initialization
- tool discovery
- tool schemas
- research state retrieval
- context retrieval
- evidence retrieval
- experiment retrieval
- memory write-back
- permission boundaries

### Context

- same research state across providers
- canonical context
- role-aware compilation
- sensitivity filtering
- token budgeting
- provenance

### Security

- secret leakage
- path traversal
- unauthorized MCP calls
- malicious parameters
- remote access disabled by default

---

# 23. PROVIDER CONTRACT TESTS

Every connector should satisfy the common contract:

```text
connect
disconnect
health
capabilities
send
stream
cancel
error normalization
```

If a provider does not support a capability, return:

```text
NOT_SUPPORTED
```

Do not fake capabilities.

---

# 24. DOCUMENTATION

Create:

```text
docs/integrations/chatgpt.md
docs/integrations/antigravity.md
docs/integrations/provider-architecture.md
docs/integrations/mcp-research-tools.md
docs/security/provider-security.md
docs/architecture/context-gateway-v3.4.md
```

Document:

```text
supported integration
account requirements
authentication
permissions
data flow
local storage
external data flow
failure behavior
provider limitations
```

---

# 25. ACCEPTANCE TEST

The following complete workflow must work:

```text
1. Open PhD-Lab.

2. Project:
   Hyperspectral Image Denoising.

3. Current state:
   HYPE-007
   EXP-021
   best PSNR = 31.42.

4. Connect ChatGPT through the supported mechanism.

5. Ask:
   "Should I test SwinIR next?"

6. Context Gateway retrieves:
   - current hypothesis
   - relevant experiments
   - previous failures
   - baseline
   - hardware constraint
   - relevant evidence

7. Only compiled context is sent.

8. Response streams into PhD-Lab.

9. Switch to Antigravity.

10. Antigravity accesses the SAME research state through MCP.

11. Ask the same question.

12. Antigravity can call:
    research.get_evidence
    research.get_failures
    research.get_experiment

13. User records the final decision.

14. PhD-Lab stores:
    decision
    provenance
    provider
    session
    evidence references

15. A later session from any provider can recover that decision.
```

---

# 26. DEFINITION OF DONE

## Architecture

- [ ] Provider-agnostic backend.
- [ ] Context Gateway.
- [ ] Canonical Research Context.
- [ ] MCP Gateway.
- [ ] Provider adapters.
- [ ] Streaming normalization.

## ChatGPT

- [ ] Official supported authentication path investigated/implemented where eligible.
- [ ] No cookie scraping.
- [ ] No private API usage.
- [ ] Streaming where supported.
- [ ] Disconnect/revoke.
- [ ] Error handling.
- [ ] API fallback disabled by default.

## Antigravity

- [ ] MCP integration.
- [ ] Research tools exposed.
- [ ] Context retrieval.
- [ ] Evidence retrieval.
- [ ] Experiment retrieval.
- [ ] Decision write-back.
- [ ] Permission boundaries.

## Context Memory

- [ ] Shared memory across providers.
- [ ] Research-state-aware retrieval.
- [ ] Evidence-aware context.
- [ ] Sensitivity filtering.
- [ ] Token budgeting.
- [ ] Role-aware compilation.
- [ ] Provenance preservation.

## Security

- [ ] Secrets protected.
- [ ] Local-only default.
- [ ] MCP authorization.
- [ ] Audit logs.
- [ ] No browser cookie extraction.
- [ ] No quota bypass.
- [ ] No unofficial provider endpoints.

## Performance

- [ ] Baseline measured.
- [ ] Post-upgrade benchmark.
- [ ] MCP latency measured.
- [ ] Context retrieval measured.
- [ ] Streaming startup measured.
- [ ] Cache effectiveness measured.

---

# 27. FINAL REPORT

Create:

```text
docs/architecture/provider-integration-v3.4-final.md
docs/architecture/context-gateway-v3.4-final.md
docs/benchmarks/multi-provider-v3.4-benchmark.md
docs/security/v3.4-security-audit.md
```

Report:

```text
1. Architecture before/after
2. ChatGPT integration
3. Antigravity integration
4. Claude Code compatibility
5. MCP architecture
6. Context Gateway
7. Context Memory changes
8. Security model
9. Streaming architecture
10. Performance benchmark
11. Test results
12. Known provider limitations
13. Policy-sensitive implementation decisions
14. Remaining work
```

---

# 28. STRATEGIC PRINCIPLE

Do NOT make PhD-Lab dependent on one AI provider.

The correct architecture is:

```text
                 PhD Research State
                         │
                  Context Memory
                         │
                  Evidence Layer
                         │
                 Context Gateway
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
       ChatGPT       Claude Code   Antigravity
```

not:

```text
PhD-Lab → ChatGPT-specific backend
```

The research state belongs to the user.

The models are replaceable.

---

# 29. FINAL INSTRUCTION TO CLAUDE

Treat this as a **backend architecture milestone**, not a UI feature milestone.

Before implementation:

```text
inspect
→ baseline
→ design
→ implement
→ test
→ benchmark
→ security audit
→ document
```

The final result should allow the user to own one persistent local research brain while using multiple first-party AI environments as interchangeable cognitive engines.

Target:

```text
              LOCAL RESEARCH BRAIN
                     │
       ┌─────────────┼─────────────┐
       ↓             ↓             ↓
   Context        Evidence      Research
   Memory         Layer         State
       └─────────────┼─────────────┘
                     ↓
              Context Gateway
                     ↓
        ┌────────────┼────────────┐
        ↓            ↓            ↓
    ChatGPT      Claude Code  Antigravity
        ↓            ↓            ↓
        └────────────┼────────────┘
                     ↓
                New Evidence
                     ↓
                Research State
```

**Milestone target: PhD Research Lab v3.4 — Multi-Provider Subscription Integration + Local Context Gateway + MCP Research Backend.**

The most important requirement is not "connect more models".

It is:

> **One persistent, provider-independent research memory that lets the user switch between ChatGPT, Claude and Gemini/Antigravity without losing research state, while keeping authentication, billing, privacy and provider-policy boundaries explicit and safe.**
