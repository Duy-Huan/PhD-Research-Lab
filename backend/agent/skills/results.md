---
name: results
title: Phân tích kết quả
description: Đọc các run đã đo, so sánh, phân tích thất bại, đề xuất bước tiếp
title_en: Results
description_en: Summarise measured results and their evidence
usage: [câu hỏi]
category: experiment
agent: research
mode: chat
risk: 1
aliases: [analyze, ketqua]
---
Analyse the measured runs in the context (metrics are MEASURED; never invent numbers). Compare against the baseline,
point out variance and missing seeds, explain failures without repeating approaches already recorded as failed, and
propose the next experiment. Propose results worth keeping as:

```phdlab-action
{"action": "record_result", "args": {"text": "…"}}
```
