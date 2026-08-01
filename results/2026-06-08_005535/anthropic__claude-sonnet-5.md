# anthropic__claude-sonnet-5

_Generated in 224.0s_

<!-- HB_META
seconds: 224.0
effort: medium
web_search: true
web_searches: 23
input_tokens: 178753
output_tokens: 15498
reasoning_tokens: 0
total_tokens: 194251
-->

<!-- BEGIN RESPONSE -->

I'll verify some specific WoW Classic fishing/cooking facts before writing this guide.# The Unkillable Angler's Playbook
### A route-based fishing/cooking doctrine for a 60 Human Warrior, Fishing 300 / Cooking 300, who literally cannot lose

Before anything else, internalize the one fact that makes your situation different from every guide ever written: **you cannot die, so the entire "danger" calculus of a spot changes.** Death isn't the threat vector for you. *Interruption* is. A rogue who sits on you with Sap/Gouge/stunlock on a PvP realm doesn't kill you — they just freeze your fishing loop indefinitely with no respawn to reset the clock. That's a worse failure state than dying, because dying ends the encounter. Getting perma-interrupted doesn't. Keep that in mind through every "AFK-safe" claim below — safety here means *freedom from interruption*, not survival.

---

## Chapter 1 — Cooking as a Force Multiplier (the actual math)

Fishing without Cooking is gathering. Cooking is where the margin lives. Here's the honest ledger at 300 Cooking, fish by fish:

| Raw Fish | Raw Value | Recipe (skill req) | Cooked Product | Why it's worth cooking |
|---|---|---|---|---|
| Raw Nightfin Snapper | vendor trash / few silver | Nightfin Soup (Cooking 250) | Nightfin Soup | Restores 841 health over 27 sec and also restores 10 Mana every 5 seconds for 10 min. Pre-TBC this is the best mana-regen food in the game, and the recipe was purchased for 2 copper from Gikkix in Tanaris — the input cost is trivial. This is the single best margin flip in your whole profession. |
| Raw Sunscale Salmon | vendor trash | Poached Sunscale Salmon (Cooking ~250) | Poached Sunscale Salmon | Restores 841 health over 27 sec and also restores 6 health every 5 seconds for 10 min. Solid non-caster raid food, sells reliably to warriors/rogues/hunters who don't want mana food. |
| Deviate Fish | near-worthless raw | Savory Deviate Delight (rare drop recipe) | Savory Deviate Delight | Savory Deviate Delight sells for 50s-1.5g EACH due to fun effects. This is a novelty item (temporary pirate/ninja transformation), not a stat food, but the margin is absurd for something made from gutter-tier fish and one vendor spice. |
| Winter Squid (seasonal, real-world winter only) | vendor trash | Grilled Squid (Cooking 240) | Grilled Squid | Restores 841 health over 27 sec, and if you eat for 10 seconds will also increase your Agility by 10 for 10 min. Good rogue/hunter/warrior-off-food, but the ingredient is only fishable in the coastal waters of Blasted Lands, Swamp of Sorrows, Badlands, Eastern Plaguelands, Tanaris and Thousand Needles in the wintertime — this is a seasonal, not permanent, gold source. Don't build a year-round plan around it. |
| Large Raw Mightfish (Feralas) | vendor trash | Mightfish Steak (Cooking 275) | Mightfish Steak | Restores 4153 health over 30 sec and also increases your Stamina by 10 for 10 min. Great tank/warrior food, reliably sellable, low competition since fewer people fish Feralas. |
| Oily Blackmouth | 15-30s raw (server-dependent) | *not a Cooking item* — feeds Alchemy | Blackmouth Oil (Alchemy 80) → Free Action Potion | You can't cook this one — it's an Alchemy reagent. Free Action Potion... people love it for PvP, and one player's server data showed a market average around 5g while costing roughly 1g38s to make, meaning the *raw fish itself* commands real value from alchemists even without you touching a stove. Sell raw, don't cook. |
| Firefin Snapper | modest raw value | Not a food recipe — Alchemy input | Fire Oil → fire resist/firepower potions | Firefin Snapper creates Fire Oil, used for spell fire damage, fire resistance, and some crafted gear. No Cooking use whatsoever. Vendor these or sell raw to alchemists — cooking them does nothing for you. |
| Stonescale Eel | high raw value, server-dependent | Not cooked — pure Alchemy | Stonescale Oil → Flask of the Titans, Greater Stoneshield Potion | Stonescale Eel is probably one of the most useful reagents for Alchemy... used to make Stonescale Oil, which in turn is used for Elixir of Superior Defense, Greater Stoneshield Potion, Flask of Petrification, and Flask of the Titans. This is your highest-value single fish, full stop — but it never touches your cookpot. Sell raw. |
| Raw Brilliant Smallfish / Longjaw Mud Snapper / Bristle Whisker Catfish | vendor trash | Cooking (early tiers) | Cheap trail food | **Explicitly not profitable.** These exist to level Cooking 1–175. Vendor the surplus or feed a hunter pet. Do not waste bag space hauling these to the AH. |

**The takeaway:** your Cooking skill is a force multiplier on exactly three fish — Nightfin Snapper, Sunscale Salmon, and Deviate Fish. Everything else in the "valuable" tier (Stonescale Eel, Firefin Snapper, Oily Blackmouth) is valuable *raw*, sold to Alchemists, and cooking would actually be a mistake because there's no recipe that improves on the raw sell price.

---

## Chapter 2 — The Route (a decision tree, not a list)

```
START HERE
│
├─ Is it currently Tue/Wed (post-reset, raid week beginning)?
│    └─ YES → Fish Azshara Bay of Storms / Feralas Verdantis River for
│              Stonescale Eel + Nightfin Snapper. Raiding guilds are
│              restocking consumables for the week. Demand peaks now.
│
├─ Is it Thu/Fri (mid-week, AH getting saturated by other farmers)?
│    └─ YES → Pivot to COOKING, not fishing. Convert your Nightfin/Sunscale
│              backlog into finished food. Sell finished goods — raw fish
│              prices dip mid-week as everyone dumps inventory; cooked
│              goods hold value because fewer people bother finishing them.
│
├─ Is it Saturday evening / Sunday (weekend prime-time, guild raids forming)?
│    └─ YES → Two options:
│              (a) If it's Sunday 2–4PM server time → STOP EVERYTHING,
│                  go to the coasts of Stranglethorn Vale for the
│                  Stranglethorn Fishing Extravaganza (see Ch.3).
│              (b) Otherwise → post finished consumables (Nightfin Soup,
│                  Mightfish Steak) NOW. Weekend raid prep = your best
│                  sell window of the week.
│
├─ Is the zone you want camped by a bot train or 15 other fishers?
│    └─ YES → Pivot zones, don't fight for pool spawns. Contested pools
│              have terrible respawn geometry when 3+ people are pulling
│              from the same 4-8 shared spawn points. Move to your
│              secondary zone (see rotation table below) instead of
│              tunnel-visioning the "best" spot that's currently dead.
│
└─ Is the market for your primary fish crashed (checked via AH addon)?
     └─ YES → Switch target fish, don't switch professions. Deviate Fish
               and Stonescale Eel rarely crash simultaneously — they
               serve different buyer bases (fun-item buyers vs.
               raiding alchemists). Diversify targets, not just zones.
```

### Weekly rotation cheat-sheet

| Day | Primary Activity | Secondary |
|---|---|---|
| Monday | Azshara Bay of Storms (Stonescale/Nightfin, night hours if possible) | Cook backlog |
| Tuesday (reset day) | Same as Monday — restock window opens | List consumables early evening |
| Wednesday | Feralas Verdantis River (Mightfish + Nightfin, lower competition) | — |
| Thursday | Cooking day — convert everything, low fishing | List cooked goods |
| Friday | Barrens Deviate Fish run (see Contrarian pick) | — |
| Saturday | AH selling window — check prices before raid formation | Light fishing only |
| Sunday | **Stranglethorn Fishing Extravaganza 2–4PM server**, then Azshara after | — |

---

## Chapter 3 — Spot Dossiers (with actual AFK-safety reasoning)

### 🐟 Azshara — Bay of Storms
- **Target:** Stonescale Eel, Raw Nightfin Snapper, Raw Sunscale Salmon.
- **Timing constraint:** Stonescale Eels are nocturnal so the best time to catch them is between the hours of 12 am and 6 am, and correspondingly Raw Nightfin Snapper's highest drop rate is between 12 a.m. and 6 a.m., while Raw Sunscale Salmon is the daytime counterpart... highest drop rate between 12 p.m. and 6 p.m. This is the one spot in the game where "what to fish" is a literal clock decision, not a preference.
- **AFK-safety:** The main coastline pools are open water away from patrol paths; Azshara's mob density along the immediate shoreline is low compared to inland. The **Bay of Storms specifically requires very high fishing skill to avoid get-aways** — the minimum is 330 with fishing pole and lure buffs... You need 425 for no fish to get away — meaning at your bare 300 skill you'll get frequent "fish gets away" messages there. Fish the general Azshara coast instead of pushing into the Bay itself unless you've stacked lures/enchants.
- **Nearest Alliance flight point:** none directly in Azshara for most of Classic (Alliance has no FP there); you fly in via Auberdine/Darkshore and ride or use a hearth. This is the spot's real weakness — a bad pull means a long run back, not a quick flight-point bail.
- **Gold/hour:** Roughly **8–20g/hour**, assuming a mid-population server, Stonescale Eel selling in the 1–3g range to alchemists, and 30–40% of your catches actually being eels rather than junk. Collapses toward the bottom of that range on low-pop or post-hype servers where raiding guilds have already stockpiled Stonescale Oil.

### 🐟 Feralas — Verdantis River / Wildwind Lake
- **Target:** Large Raw Mightfish, Raw Nightfin Snapper.
- **AFK-safety:** Inland river/lake fishing, minimal hostile mob traffic compared to coastal zones, and Feathermoon Stronghold is a short flight/ride away for reagents and selling. Lower player traffic than Azshara because fewer guides push it — this is a quieter, less-contested version of the same high-tier fish pool.
- **Gold/hour:** **6–14g/hour.** Lower ceiling than Azshara because Mightfish Steak demand is niche (mostly Darkmoon Faire buff-run stockpiling), but steadier because almost nobody else is farming it. Collapses if you hit the recipe wall — Recipe: Mightfish Steak has limited stock and random respawn times at the Feralas vendors, so you may be capped by recipe access, not fish supply.

### 🐟 Booty Bay / Stranglethorn Vale coast — weekly event window
- **The event:** Every Sunday from 2:00 PM to 4:00 PM server time along the coasts of Stranglethorn Vale, be the first player on your server to catch 40 Speckled Tastyfish from special "Speckled Tastyfish School" pools and turn them in to Riggle Bassbait in Booty Bay, with rewards up to Hook of the Master Angler (a trinket that turns you into a fish for underwater breathing and swim speed) for the winner, and consolation prizes for everyone else who participates.
- **AFK-safety:** This is a *two-hour window activity*, not an AFK farm — you need to be actively clicking during the event itself. But it's the highest-value two hours in your entire week: even non-winning participation yields rare fish and gold, and Booty Bay's neutral status means **you can sell overflow Deviate Fish, Stonescale Eel, and cooked goods to Horde buyers on the neutral AH immediately after**, no faction tax on opportunity.
- **Gold/hour (event window only):** Highly variable, **15–50g** for the 2-hour block depending on whether you place in the top rewards; treat this as a lottery-ticket bonus on top of your baseline route, not a reliable hourly rate.

### 🐟 Dustwallow Marsh — Theramore Isle inland ponds
- **Target:** early Nightfin/Sunscale practice, Bristle Whisker Catfish backfill, and it's the required zone for the one-time **Nat Pagle, Angler Extreme** quest — Nat Pagle wants you to catch fish from the Misty Reed Strand, Sar'theris Strand, Verdantis River, and Savage Coast of Stranglethorn — this is a **one-time unlock, not a daily.** Vanilla/Classic-era has no fishing dailies at all; don't structure your week around a "Nat Pagle daily" the way TBC/retail guides do, because it doesn't exist in Classic.
- **AFK-safety:** This is about as safe as fishing gets — Theramore is a friendly hub town, the pond is inside town limits, flight point is 15 feet away, and there is essentially zero hostile mob traffic. Ideal for genuinely walking away from the keyboard for extended stretches.
- **Gold/hour:** **3–8g/hour.** Low ceiling — this zone is for skill progression and the one-time quest unlock, not sustained profit. Don't camp here long-term once you've got what you need.

### 🐟 Winterspring — Everlook lake shoreline
- **Target:** high-tier fish overlap zone (Nightfin/Sunscale/Stonescale-adjacent pools), Winter Squid during real-world winter months only.
- **AFK-safety:** Everlook is an Alliance-friendly goblin neutral town with a flight point directly in it. The lake right at town edge has negligible mob patrol density. This is your best "log in, tab out, come back in three hours" spot on the whole list.
- **Gold/hour:** **5–12g/hour**, lower than Azshara/Feralas because fewer buyers actively shop Winterspring-tagged fish, but the safety margin is the best on this list — pick this spot specifically on days you genuinely cannot supervise the client at all.

---

## Chapter 4 — The Auction House Economy Cycle (AEC)

Every "sell for X gold" number in a guide is a snapshot, not a law. Three forces move your fish/food prices every week:

1. **Raid reset (Tue/Wed).** Guilds restock consumables right after reset for the week's clears. Stonescale Eel and Nightfin Snapper prices spike Tue–Thu, then decay through the weekend as guilds finish shopping.
2. **Weekend raid nights (Fri/Sat/Sun).** Panic-buys happen here — someone forgot flasks, and last-minute food/potion prices spike above midweek baseline. This is your best *cooked goods* selling window, not your best fishing window (you should already have inventory built up).
3. **Patch/content cycles.** New raid tiers or phase releases spike demand for specific consumables overnight (a new tank-check boss = Greater Stoneshield Potion demand spikes = Stonescale Eel raw price spikes even though you don't touch Alchemy). Watch patch notes, not just your own market history.

**What collapses your estimates:** a server-wide botting wave crashing raw fish prices (this happens constantly with Stonescale Eel specifically since it's bot-favorite due to high value), a population-tier shift (a server bleeding population late in a content cycle sees AH liquidity dry up — your listings sit unsold for days), or simply being on a low-pop or "dead" realm where there simply aren't enough active raiding guilds to create Stonescale/Nightfin demand at all. If your server is low-pop, cut every gold/hour estimate above roughly in half and lean harder into the Deviate Fish "fun item" market instead, since that demand comes from casual players, not raid logistics, and holds up better on quiet servers.

---

## Chapter 5 — The Contrarian Pick: Barrens Oases, Deviate Fish, on an Alliance character

Every generic guide tells Alliance players to skip Deviate Fish farming because The Barrens is Horde territory, [so] Alliance players might find Deviate Fish and its recipe sell for more on their faction's AH, making it a lucrative (though potentially dangerous) farm — and then dismisses it as "potentially dangerous" and moves on. That dismissal assumes death matters to you. **It doesn't.** You cannot die. The entire risk premium every guide attaches to this spot evaporates for your specific character, while the reward — Alliance-side AH scarcity of Deviate Fish and its recipe — remains fully intact.

Here's why I think this is underrated specifically for you:
- The best place to catch Deviate Fish is from School of Deviate Fish, small pools found in each of the three oases in The Barrens, and the surrounding mobs at the northwest oasis are level 12-13 mobs who patrol near the pond — trivial for a level 60. Even if you pull aggro while tabbed out, you take a few seconds of chip damage from a level 12, not a threat, and it will not kill a level 60 warrior in any scenario.
- Since you cannot die, "griefing" from Horde players downgrades from "corpse camp for an hour" to "mildly annoying stun/kill-and-move-on," and most low-level Horde players in the Barrens have zero incentive to camp a level 60 who just keeps standing back up.
- Deviate Fish and Savory Deviate Delight sell as **novelty/fun items** to a buyer base that has nothing to do with raid logistics, meaning this income stream is uncorrelated with the AEC cycle described above — it's a genuine diversification play, not just another Stonescale Eel clone.

The catch: Deviate Fish schools are shared across three oases with only four total spawn points, so if another player (Alliance or Horde) is already working the same oasis, you may need to hop between all three locations to find an open pool — plan on some travel time between oases rather than expecting to park in one spot indefinitely.

---

## Chapter 6 — Failure Modes (what every guide forgets to warn you about)

1. **Chasing the "best" fish instead of the best *available* fish.** The guide tells you Stonescale Eel is worth the most, so you camp Azshara for six hours waiting for night-cycle pools that three other people are also fishing. The player who pivots to whatever pool is actually open makes more gold/hour than the player perfectly executing a "correct" but contested route.
2. **Cooking backlog rot.** Fishing is easy to automate mentally; cooking is not — it requires standing at a fire and clicking. Players stockpile thousands of raw Nightfin Snapper and never actually convert them, leaving 90% of the theoretical profit margin from Chapter 1 unrealized. If you're not converting at least weekly, you're running a fishing hobby, not a cooking-fishing business.
3. **Ignoring recipe scarcity as a hard cap.** Several of the best recipes (Mightfish Steak, Nightfin Soup, Savory Deviate Delight) are **limited-stock vendor items or rare drops**, not infinitely available. A guide that tells you "just cook X" without checking whether you've actually learned the recipe, or whether the vendor has restocked, is giving you a plan you can't execute. Confirm recipe ownership *before* you build three days of fishing around a dish you can't cook yet.
4. **(Bonus, specific to your character) Mistaking "cannot die" for "cannot be interrupted."** As covered up top — the actual AFK risk for you is combat/interruption loops, not death. A spot with low mob density but frequent PvP flagging on a contested-zone border can quietly waste far more of your unlimited time than a "dangerous" but empty zone ever would.
