---
name: code
title: Viết code
description: Giao tác vụ code cho coding provider (Claude Code / Codex / Gemini / Antigravity) hoặc mô hình của ứng dụng
usage: <tác vụ>
category: experiment
agent: research
mode: run
pipeline: code
provider: coding
risk: 2
aliases: [implement]
---
Implement exactly the task described, with a small test or a smoke run. Write only new files under the run folder;
print the command that runs it in a ```phdlab-run``` block.
