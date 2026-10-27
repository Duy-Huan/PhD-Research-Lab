"""Native tool capability system (v6.6.0): the environment provides tools; the agent decides how to use them.

  spec        ToolSpec, structured ToolError, semantic versions/constraints
  schema      bounded JSON Schema validation for specs, inputs and outputs
  registry    central versioned registry: builtin + manifest + external MCP tools, search, lazy describe, availability
  adapters    native / python / cli / mcp / container execution behind one contract
  runtime     unified execution: grants, budgets, async jobs, streamed observations, timeout/cancel, retry, provenance
  agent_loop  model-driven discovery/selection/chaining/recovery with verified execution claims
  proposals   agent-proposed tools: sandbox implementation, validation, promotion, rollback
"""
