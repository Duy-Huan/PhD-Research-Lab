---
name: hypothesis
title: Giả thuyết
description: Đề xuất giả thuyết có thể kiểm chứng (bạn duyệt từng giả thuyết)
usage: [hướng / gap]
category: research
agent: research
mode: chat
risk: 1
aliases: [hypotheses, gt]
---
Propose two or three falsifiable hypotheses for the current direction. Each: statement, prediction with a metric and a
threshold, the baseline it is compared to, and the cheapest experiment that could refute it. Propose each one as:

```phdlab-action
{"action": "create_hypothesis", "args": {"text": "…"}}
```

Do not repeat hypotheses or failed approaches already recorded in the context.
