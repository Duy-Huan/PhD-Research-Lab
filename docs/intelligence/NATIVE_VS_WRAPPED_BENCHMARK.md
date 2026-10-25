# Native versus wrapped benchmark

`tools/provider_fidelity_benchmark.py` runs three deterministic tasks twice each: arithmetic, extraction from supplied data and refusal to invent an absent measurement. Both native LM Studio and wrapped HTTP chat request `spark-x2.5-4b`, temperature 0.3 and bounded output. Responses are real.

The [first attempt](../qa/evidence/2026-10-25/native-vs-wrapped/report.json) passed 5/6 native and 5/6 wrapped requests; two requests errored because the model was unloaded. Their cause is not established. The [serial rerun](../qa/evidence/2026-10-25/native-vs-wrapped-serial/report.json), after competing suites ended, passed 6/6 native and 6/6 wrapped.

The native minimal system prompt differs from the application prompt by design. The provider-returned native model ID was available; the wrapper did not expose authoritative returned model ID or token usage. Those fields stay unknown. This small sample establishes these oracles only, not universal intelligence preservation, scientific quality, latency guarantees or sustained reliability.
