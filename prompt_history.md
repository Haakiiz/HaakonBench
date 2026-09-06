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

---

## 2026-07-24 — Six-mandate version (c96c9b), retired 2026-09-06

The prompt the `pc96c9b__medium__search-on` bucket was answered with (14 models,
2026-07-09 → 2026-08-14) and the basis for the README write-ups through Grok 4.6 /
Gemini 3.7. Retired in favour of the open-format rewrite now live in `haakonbench.py`
(`a7b352`), which drops the six numbered mandates so structure becomes the model's
decision rather than the prompt's.

Known defect: **"AEC (Auction House Economy Cycle)" is not a real WoW Classic term** —
it originated in this prompt. Ten of the fourteen answers built a named section around
it, and the grader then penalised at least one of them for "generic 'AEC' warnings".
The prompt planted the hallucination the rubric punished. Verbatim copy also lives at
`results/pc96c9b__medium__search-on/_prompt.md`.

### PROMPT

```
You are writing a WoW Classic fishing guide for a specific character: level 60 Human Warrior, Alliance faction, Fishing 300, Cooking 300. The character has unlimited time to fish but cannot die and cannot babysit the game — every recommended spot must be genuinely AFK-safe for extended sessions.

Your job is not to write a competent guide. Your job is to write the BEST guide this character will ever read. That means:

1. ROUTE OVER SPOT LIST — Do not give a flat list of zones. Design an actual rotation or decision tree: what to fish Monday morning vs. Saturday evening, what to do when a zone is camped, how to pivot if a market crashes. A guide that ignores the AEC (Auction House Economy Cycle) is a guide that leaves gold on the table.

2. COOKING AS A FORCE MULTIPLIER — Identify every recipe at 300 cooking that converts cheap fish into items worth materially more. Give concrete before/after valuations (e.g., "Spotted Yellowtail vendor trash → Grilled Squid sells for X per stack on a typical server"). Show the math. If a fish has no profitable cooking use, say so explicitly and recommend vendoring or another use.

3. GOLD/HOUR WITH HONEST UNCERTAINTY — Give a gold/hour figure for each recommended spot. Do not invent false precision. Format it as a range with stated assumptions (e.g., server population tier, time of day, AH saturation). Explain what collapses the estimate downward.

4. AFK-SAFETY ANALYSIS — For every spot you recommend, state WHY it is safe: patrol paths, respawn geometry, nearest Alliance flight point, whether a PvP player could grief you while you shower. Do not just say "safe zone" — explain the safety.

5. ONE CONTRARIAN RECOMMENDATION — Recommend at least one spot or strategy that most guides ignore or actively dismiss, but that you believe is underrated for this specific character. Defend it with specifics.

6. FAILURE MODES — What are the top 3 ways a player following your guide would still underperform? What mistakes does every fishing guide fail to warn about?

You control the structure. Use whatever format — chapters, tables, decision trees, callout boxes — that makes this genuinely more useful than a wall of text. Length should be determined by the content, not by an attempt to seem thorough.

Do not hedge everything. Make claims. Be wrong confidently if you must. A guide full of "it depends" is useless.
```
