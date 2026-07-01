# LLM Benchmark Evaluation: WoW Classic Fishing & Cooking Guide (Level 60 Human Warrior)

## Evaluation Matrix

| Letter | Accuracy | Strategy | Creativity | Structure | Fidelity | Total | One-line verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **A** | 1 | 2 | 2 | 4 | 3 | **12** | A disaster of hallucinated fish, fake recipes, and absurd gold claims. |
| **B** | 5 | 5 | 4 | 5 | 5 | **24** | Decent structure but suffers from major geographic and recipe inaccuracies. |
| **C** | 6 | 6 | 5 | 6 | 7 | **30** | Thorough but plagued by multiple recipe and buff stat hallucinations. |
| **D** | 10 | 10 | 10 | 10 | 10 | **50** | Flawless. Brilliant strategy, perfect accuracy, and masterful prompt integration. |
| **E** | 8 | 6 | 6 | 5 | 6 | **31** | Realistically safe instance-farming advice, but lacks structural depth. |
| **F** | 7 | 6 | 5 | 6 | 6 | **30** | Clean formatting and good safe spots, but misses critical prompt requirements. |
| **G** | 6 | 4 | 3 | 4 | 4 | **21** | Extremely generic LLM-style list with no real strategic depth. |
| **H** | 8 | 7 | 5 | 7 | 6 | **33** | A highly competent and realistic guide, but plays it too safe and generic. |
| **I** | 3 | 4 | 3 | 4 | 4 | **18** | Riddled with geographic hallucinations and mechanically impossible suggestions. |

---

## Rankings (Best to Worst)

1. **Response D**: The absolute gold standard. It displays flawless accuracy, realistic gold estimates, a brilliant contrarian strategy, and a highly functional structure that directly answers the prompt.
2. **Response H**: Extremely competent and realistic. It understands the day/night cycle and provides honest gold estimates, but plays it too safe and misses the contrarian and failure-mode requirements.
3. **Response E**: Solid and practical. Recommending the Wailing Caverns instance for safe AFK Deviate Fish farming is excellent, but the guide lacks structural depth and misses the weekly route logic.
4. **Response C**: Highly detailed, but held back by numerous minor hallucinations regarding recipe names and stat buffs.
5. **Response F**: Visually clean, but hallucinates items (Aquadynamic Fish Lens) and lacks the required decision-tree route, contrarian pick, and failure modes.
6. **Response B**: Good structural attempt, but fundamentally fails geography by placing saltwater Stonescale Eels in the Plaguelands.
7. **Response G**: A generic, low-effort list of zones that completely ignores the specific constraints of the prompt.
8. **Response I**: Heavily hallucinated. Suggests fishing in dry areas (The Quagmire), non-existent caves, and using impossible macros (auto-casting Battle Shout while standing still).
9. **Response A**: An absolute failure. Hallucinates entirely fake fish (Azurewing Perch, Ahi Tuna), fake recipes, and claims an impossible 300g/hour.

---

## Winner Declaration

**Response D** is the undisputed winner, separating itself from the competition by a massive margin. While other models fell into the trap of generic "zone lists" and wild hallucinations, Response D demonstrated an intimate, flawless grasp of WoW Classic mechanics. 

What truly sets Response D apart is its brilliant execution of the **Contrarian Recommendation**. It weaponizes the user's specific constraint—that the character *cannot die*—to recommend the Barrens Oases for an Alliance character:
> "Since you cannot die, the risk premium every guide attaches to this spot evaporates for your specific character, while the reward—Alliance-side AH scarcity of Deviate Fish and its recipe—remains fully intact."

Furthermore, its **Strategy Depth** is unmatched. It includes a highly functional ASCII decision tree for the Auction House Economy Cycle (AEC), provides completely honest and realistic gold-per-hour ranges (8–20g/hr), and accurately identifies that Stonescale Eels do not have a cooking recipe and must be sold raw to alchemists. This is an elite, human-grade guide.

---

## Hallucination Callouts

*   **Response A**: Massive hallucinations. **Azurewing Perch**, **Ahi Tuna**, and **Yellowfin Grouper** do not exist in WoW Classic. It claims Azurewing Perch cooks into Grilled Squid (Grilled Squid uses Winter Squid). It also claims Mild Spices cost 1-2g from a vendor (they cost copper).
*   **Response B**: Claims **Stonescale Eel** pools spawn in the Eastern and Western Plaguelands (Stonescale Eels are strictly saltwater coastal fish). Claims Summer Bass cooks into Sunscale Salmon (Summer Bass cooks into Hot Smoked Bass).
*   **Response C**: Hallucinates multiple recipes and buffs. "Grilled Yellowtail" and "Grilled Mightfish" do not exist. Claims Mightfish Steak gives +20 Strength (it gives +10 Stamina/Spirit). Claims Whitescale Salmon cooks into Poached Whitescale Salmon with frost resist (it cooks into Baked Salmon).
*   **Response F**: Recommends "Aquadynamic Fish Lens" (+100 skill for 10 mins), which does not exist in WoW Classic (the item is the Aquadynamic Fish Attractor, which lasts 5 minutes).
*   **Response I**: Hallucinates **"Hidden Zul'Gurub Shore"** south of Grom'gol (Zul'Gurub is an inland instance). Claims Winter Squid is a night fish (it is caught during the day). Claims Winter Squid cooks into Hot Smoked Bass. Recommends fishing in **"The Quagmire"** in Dustwallow (a muddy inland area with no fishable water) and a non-existent cave in southern Wetlands. Suggests auto-casting **Battle Shout** while AFK fishing (Battle Shout requires rage, which cannot be generated while standing still).

---

## Generic-Response Penalty List

*   **Response B**: Failed on strategy depth and creativity by offering a standard "zone 1, zone 2" list without a dynamic weekly decision tree or a truly contrarian recommendation.
*   **Response C**: Fell into the standard template of listing gear and zones without a true decision-tree route. The gold estimates lacked detailed server-type assumptions.
*   **Response E**: Did not include a weekly schedule, decision tree, or failure-mode analysis, opting instead for a brief bulleted summary.
*   **Response F**: Completely ignored the prompt's demand for a route/decision tree, a contrarian recommendation, and a failure-mode analysis. It is a standard "spot list" disguised with clean markdown.
*   **Response G**: The epitome of a generic LLM response. It provided flat lists of zones, vague gold estimates, and no unique mechanical insights or structural innovations.
*   **Response I**: Used decorative headers to mask a highly generic, inaccurate, and mechanically impossible guide. It failed to provide a realistic AEC cycle or genuine failure modes.

---

## Key (revealed after grading)

- **A** → `anthropic__claude-haiku-4-5`
- **B** → `anthropic__claude-opus-4-8`
- **C** → `anthropic__claude-sonnet-4-6`
- **D** → `anthropic__claude-sonnet-5`
- **E** → `google__gemini-3.1-pro-preview`
- **F** → `google__gemini-3.5-flash`
- **G** → `openai__gpt-5.4-mini`
- **H** → `openai__gpt-5.5`
- **I** → `xai__grok-4.3`

---

## Efficiency — raw data

_Same score with fewer tokens or less time = more efficient. Reasoning tokens are internal thinking; '—' means the provider didn't report it. Web searches = queries the model actually ran (— if not exposed, e.g. xAI)._

| Model | Total score | Time (s) | Output tok | Reasoning tok | Total tok | Web searches |
|---|---|---|---|---|---|---|
| `anthropic__claude-haiku-4-5` | — | 64.4 | 5,953 | 0 | 6,141 | — |
| `anthropic__claude-opus-4-8` | — | 75.3 | 4,350 | 0 | 4,601 | — |
| `anthropic__claude-sonnet-4-6` | — | 171.4 | 7,636 | 0 | 7,824 | — |
| `anthropic__claude-sonnet-5` | — | 224 | 15,498 | 0 | 194,251 | 23 |
| `google__gemini-3.1-pro-preview` | — | 27.8 | 1,244 | 1,005 | 2,427 | — |
| `google__gemini-3.5-flash` | — | 27.6 | 2,711 | 1,699 | 4,588 | — |
| `openai__gpt-5.4-mini` | — | 37.4 | 4,783 | 1,840 | 4,960 | — |
| `openai__gpt-5.5` | — | 116.5 | 5,345 | 682 | 5,522 | — |
| `xai__grok-4.3` | — | 10.9 | 1,258 | 731 | 2,290 | — |