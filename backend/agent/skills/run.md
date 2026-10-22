---
name: run
title: Chạy thí nghiệm
description: Chạy một lệnh trong code project (venv; Docker khi cần Linux), có guard phần cứng và kiểm chứng metrics
title_en: Run
description_en: Run a command in the project environment
usage: <lệnh> [--gpu]
category: experiment
agent: research
mode: run
pipeline: experiment
provider: app
risk: 2
aliases: [exec, train]
---
The command runs from the root of the open code project. Metrics are read from $RUN_DIR/metrics.json or parsed from
the output; a run without valid metrics is never marked completed.
