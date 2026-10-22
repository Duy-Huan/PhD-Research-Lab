---
name: remember
title: Ghi nhớ
description: Đề xuất lưu một quyết định / phát hiện vào bộ nhớ dự án (bạn duyệt)
title_en: Remember
description_en: Save a decision, finding or question to project memory
usage: <nội dung>
category: system
agent: research
mode: chat
risk: 1
aliases: [memo, nho]
---
Turn what the researcher wrote into one precise memory item (type: decision, finding, hypothesis, open_question or
rejected_approach) and propose it:

```phdlab-action
{"action": "propose_memory", "args": {"type": "decision", "text": "…"}}
```
