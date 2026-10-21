---
name: verify
title: Kiểm chứng claim
description: Đối chiếu từng claim/số liệu với các run đã đo — claim không có bằng chứng bị đánh dấu
title_en: Verify
description_en: Check claims against sources and measured results
usage: [đoạn văn hoặc file]
category: writing
agent: reviewer
mode: run
pipeline: verify
provider: app
risk: 0
aliases: [check, factcheck]
---
Every numeric claim must match a measured run; every citation must exist in the library. Unsupported claims are listed,
never silently accepted.
