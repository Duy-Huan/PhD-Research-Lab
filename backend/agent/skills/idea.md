---
name: idea
title: Chạy thử ý tưởng
description: Ý tưởng → kế hoạch → code → chạy thử (venv, guard phần cứng) → kiểm chứng metrics → báo cáo
title_en: Try an idea
description_en: Quickly test an idea as a small experiment
usage: <ý tưởng>
category: experiment
agent: research
mode: run
pipeline: idea
provider: app
risk: 2
aliases: [try, thu]
---
Keep the prototype small: it must finish in a few minutes on one RTX 3060 (or CPU), use synthetic or tiny data unless
the researcher names a local dataset, set a seed, print progress, and write its final metrics as JSON to
$RUN_DIR/metrics.json. Expose --batch-size so an out-of-memory error can be recovered automatically.
