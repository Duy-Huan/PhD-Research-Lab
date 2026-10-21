---
name: science
title: OpenScience task
description: Giao một tác vụ khoa học có phạm vi rõ cho runtime OpenScience đã cấu hình
usage: <task and expected outputs>
category: research
agent: research
mode: run
pipeline: research
provider: openscience
risk: 2
---
Delegate this bounded scientific task to the configured external OpenScience engine.
OpenScience discovers and uses its native scientific skills and tools. Do not copy
its skill library into PhD Lab or replace it with an extra local agent loop.
Keep evidence and uncertainty explicit. Code, compute and external actions require
the configured permissions. Return a cited report and save durable Results for any
files that should be collected. A finished agent turn is not a verified experiment.
