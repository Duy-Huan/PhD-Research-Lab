---
name: gap
title: Khoảng trống nghiên cứu
description: Phân tích research gap từ đề cương, thư viện và kết quả đã có
usage: [phạm vi]
category: research
agent: research
mode: chat
risk: 1
aliases: [gaps]
---
Identify research gaps for this project from the outline, the library, decisions and measured runs in the context.
For each gap: what is missing, why it matters, which sources show it (ids from the context; otherwise "cần kiểm chứng"),
how an experiment on one RTX 3060 could test it, and the risk that it is not novel. Propose the strongest one or two as
action blocks the researcher can accept:

```phdlab-action
{"action": "propose_gap", "args": {"text": "…"}}
```
