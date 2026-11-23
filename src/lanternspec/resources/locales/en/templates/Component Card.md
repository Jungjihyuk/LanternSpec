---
id: ${id}
type: component
status: ${component_status.watching}
component: "${component}"
kind: ${kind}
created: ${today}
updated: ${today}
links: ${links}
template: Component Card
template_version: 1.0.0
based_on: 1.0.0
---
# 🧩 ${id} ${name}

> [!abstract] At a glance
> {{Why this component was added, in one line (required)}}

## What
> [!guide]- ✍️ How to write — where and how it is connected
> The name and kind are in the properties above. Here, write where and how it is connected (this project only or all your projects, with which settings).

{{Where and how it is connected (required)}}

## Why — the problem
> [!guide]- ✍️ How to write — which earlier problem it answers
> What was inconvenient or wrong, as facts. Example: "Notion notes were found by title only, so a note that exists was judged missing (🔴)".

{{The problem (required)}}

## Expected effect
> [!guide]- ✍️ How to write — the goal and the bar for success
> What should change once this is added. Write the bar, so that later you can say "it worked" or "it didn't".

{{The expected effect and the bar for success (required)}}

## Measure
> [!guide]- ✍️ How to write — what to look at
> Pick from: number of calls · time taken · tokens · check errors · retro lines · review findings. In the value column write "this much is enough". `lantern eval` shows the ones that code can measure.

| What to look at | Target value |
|---|---|
| {{What to measure (required)}} | {{Target value}} |

## Cost
> [!guide]- ✍️ How to write — what you accept
> The time, money or hassle that may grow because of this. Example: "up to twice the time per call is fine".

{{The cost you accept}}

## Review time
> [!guide]- ✍️ How to write — when to look again
> A date, or "after 10 works". If you set none, there is nothing to look back at.

{{When to look again (required)}}

## Review result
> [!guide]- ✍️ How to write — a person writes it at the review
> Keep, drop or keep watching, and why. Then change the `status` property above to the same value. If it differed from what you expected, write what you saw.

{{Review result}}

<!-- lantern:template-only -->
## Changelog
| Version | Date | What changed |
|---|---|---|
| 1.0.0 | 2026-11-24 | Base template |
