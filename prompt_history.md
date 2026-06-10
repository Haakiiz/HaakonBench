# Prompt History

Old versions of `PROMPT`, `GRADER_SYSTEM_TEMPLATE`, and `GRADER_RUBRIC` from `haakonbench.py`.

---

## 2026-06-10 — Original prompts (replaced by creativity-focused rewrite)

### PROMPT

```
I want you to create me a fishing strategy, as a level 60 human warrior on World of Warcraft Classic servers. I must be able to fish for an extended period of time where i am not killed and do not have to move. That is alliance zones, or maybe very hidden areas in contested zones. I have level 300 fishing and level 300 cooking, so please utilize both for maximum gold/hour. Tell me where to fish, when, what, etc. Give an estimated gold / hour for the different zones and areas and fish.

Be creative in giving me a great guide, you can add 'features'/chapters/stuff as youd like, if you think that would improve the end result. You are not hard limited by this prompt, but catch the essence of it and work on it. Your overarching goal is to impress me
```

### GRADER_SYSTEM_TEMPLATE

```
You are an expert evaluator for LLM benchmarks. You grade responses blind — the identities of the models are hidden behind letters (A, B, C, ...). Be rigorous, specific, and honest. Reward accuracy, depth, creativity, structure, and usefulness. Penalize hallucinations (especially WoW Classic facts that look made up), generic filler, and prompt-ignoring.

CRITICAL RULE FOR ACCURACY SCORING: When checking WoW Classic facts, use ONLY the Verified Reference Data section below as your source of truth. Do NOT rely on your own knowledge for recipes, buff stats, ingredients, or vendor locations — it may be wrong. If a claim cannot be verified against the reference data, mark it as 'unverifiable' rather than calling it incorrect. Pay special attention to the 'Common LLM Hallucinations' list — these are known errors that look plausible but are wrong.

{reference_data}
```

### GRADER_RUBRIC

```
You will judge multiple LLM responses to the SAME user prompt.

# The original user prompt
{prompt}

# The responses (anonymized)
{responses_block}

# Your task
For EACH response, score it on these dimensions (1-10 each):
- Accuracy        — Is the WoW Classic info plausible and correct? (zone safety, fish types, cooking recipes, vendor prices)
- Strategy depth  — Does it actually maximize gold/hour with concrete numbers and reasoning?
- Creativity      — Did it add interesting structure / 'features' beyond the literal ask?
- Structure       — Is it well-organized, scannable, useful as a reference?
- Prompt fidelity — Did it respect the constraints (lvl 60 Alliance warrior, AFK-safe, 300/300)?

Then:
1. Produce a markdown table with one row per response: | Letter | Accuracy | Strategy | Creativity | Structure | Fidelity | Total | One-line verdict |
2. Rank the responses from best to worst.
3. Declare a winner and explain in 3-5 sentences WHY that one beat the others.
4. Call out any specific hallucinations or factual errors you spotted, by letter.

Be opinionated. No participation trophies.
```
