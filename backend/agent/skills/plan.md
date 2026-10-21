---
name: plan
title: Thiết kế thí nghiệm
description: Thiết kế thí nghiệm (dữ liệu, baseline, metric, seed, ngân sách GPU)
usage: [giả thuyết]
category: experiment
agent: research
mode: chat
risk: 1
aliases: [design]
---
Design the experiment for the chosen hypothesis: dataset and split, baseline(s) trained under the same budget, metrics,
seeds (≥3 for any claim), ablations, a compute budget that fits an RTX 3060 12 GB (batch size, precision, epochs),
and the stopping rule. Record it as an experiment the researcher can accept:

```phdlab-action
{"action": "create_experiment", "args": {"title": "…", "method": "…"}}
```

Finish by suggesting `/idea …` to prototype it immediately, or `/run <command>` if the code already exists.
