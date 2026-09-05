# Model API configuration

OpenAI is optional and not required.

## Recommended default

The agent uses a weighted model pool:
- **Qwen3.7 Plus** — primary, weight 3
- **DeepSeek-V4-Flash** — fallback, weight 2

Fireworks currently lists Qwen3.7 Plus at about **$0.40 / 1M input tokens**
and **$1.60 / 1M output tokens**. DeepSeek-V4-Flash is listed at about
**$0.14 / 1M input tokens** and **$0.28 / 1M output tokens**.
Prices may change.

## Environment

```bash
FIREWORKS_API_KEY=your_rotated_key
USE_MODEL=true
MODEL_TARGETS=qwen=accounts/fireworks/models/qwen3p7-plus:3,deepseek=accounts/fireworks/models/deepseek-v4-flash:2
```

Never commit API keys to source control. A key pasted into chat should be rotated.

## Human-in-the-loop

The agent generates the job URL, tailored resume, cover letter when useful,
and application notes. It does **not** automatically submit applications.
