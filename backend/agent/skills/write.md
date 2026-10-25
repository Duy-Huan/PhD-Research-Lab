---
name: write
title: Viết bài
description: Viết / sửa một phần của bài báo theo yêu cầu và văn phong của bạn (bạn duyệt trước khi lưu)
title_en: Write
description_en: Write / revise a paper section in your style (you approve before it is saved)
usage: <phần> [yêu cầu văn phong]
category: writing
agent: research
mode: chat
risk: 1
aliases: [draft, viet, paper]
---
Write the requested paper section in the style the researcher asks for (venue, tone, length, tense, terms to use or
avoid). Use only results that are MEASURED or pinned in the context and cite only sources from the project library
(\cite{key}); write [CẦN KIỂM CHỨNG] where evidence is missing instead of inventing it. Output LaTeX body text
without the section command. Show the text, then propose saving it:

```phdlab-action
{"action": "write_section", "args": {"section": "experiments", "text": "…"}}
```

Sections: abstract, introduction, related_work, methodology, experiments, discussion, conclusion.
