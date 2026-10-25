---
name: taleweaver-adventure-creator
description: Generates TaleWeaver adventure concepts (Story Idea text for the World-Builder) with a gripping story, a planted twist and non-trivial puzzles that the engine can actually enforce. Uses Sequence, Scene, NPC, Item, Sidequest and Award tags and knows the parser's and engine's limits.
---

# TaleWeaver Adventure Creator

Use this skill to write, brainstorm or refine the **Story Idea & Context** text that the user pastes into the World-Builder. The World-Builder (an LLM) turns it into a playable adventure. Your text has two jobs:

1. **Tell a story worth playing**: stakes, a memorable antagonist, escalation and a twist.
2. **Only ask for things the engine can enforce.** If a puzzle or a turning point depends on something the engine cannot check, it falls apart in play: the GM improvises, players skip it or get stuck.

Work in this order: premise → twist → chapter skeleton → puzzles → design checklist → output.

---

## 1. How the World-Builder reads your text

The parser is simple and literal. Respect it exactly.

- Text **before the first `[Sequence: N]`** is the premise. It goes into the generation prompt as is. Put the world, protagonist, tone, twist plan and design rules there.
- Each `[Sequence: N] Title` starts a chapter block that runs until the next `[Sequence]` tag. At most 15 are parsed, numbered 1..N in order of appearance.
- In each chapter block, **only these line prefixes are extracted** (case-insensitive, at the start of a line):
  - `Required Item: ITEM_ID`: the chapter completes once the player holds this item.
  - `Required Scene: SCENE_ID`: the chapter completes while the player is in this scene.
  - `Defeat NPC: NPC_ID`: the chapter completes once this NPC is defeated.
  - `End Condition: <text>`: the narrative completion condition.
- Every other line of the block (including `[Scene]`, `[NPC]` and `[Item]` tags placed inside it) becomes the chapter's **walkthrough** (in full) and its **description** (first 500 characters). So write the chapter's real solution steps inside its block, and put the most important GM guidance first.
- **Parser traps.** A line starting with `Item:`, `Item ID:`, `Key Item:`, `Scene:`, `Target Scene:`, `Condition:`, `Completion Condition:`, `Defeat:` or `Defeated NPC:` is *also* read as a hard rule. Never start prose lines with those words. Tags in brackets (`[Scene: 2] ...`) are safe.
- IDs in hard rules are upper-cased. Use `UPPER_SNAKE_CASE` IDs and introduce every referenced ID as an entity (`[Item: ...] Rusty Shiv (RUSTY_SHIV)`) so the builder creates it with exactly that ID.
- `[Sidequest]`, `[Award]` and everything not listed above are **not parsed**. They are guidance for the builder LLM, so phrase them clearly.
- Everything after the last `[Sequence]` tag belongs to the last chapter's block. So put `[Sidequest]` and `[Award]` tags in the premise, **before** `[Sequence: 1]`, or they end up in the final chapter's walkthrough.

### When a chapter completes
- With one or more hard rules (`Required Item/Scene`, `Defeat NPC`, or a guard the builder adds), the chapter completes **as soon as all of them are true**, deterministically. The `End Condition` is then only flavour.
- Without hard rules, the GM decides when the `End Condition` has happened. That is fine for social or story beats, but less reliable.
- **Pitfall:** a hard rule that is already true when the chapter begins completes it instantly (the player already holds the item or is already standing in the scene). Pick items that only become obtainable in this chapter and scenes the player has not reached yet.
- Chapters are strictly **linear**: one active chapter, no branches, no parallel arcs. Branching lives *inside* chapters (choices, soft rules, variables), not in the chapter list.

---

## 2. What the engine can and cannot do

**Can enforce deterministically (use these for every puzzle that matters):**

| Mechanic | Notes for your design |
| :--- | :--- |
| Locked **exits** | Code, key item or narrative condition; optional script guard. A code is typed into a lock dialog, so it must be an exact string or number. |
| **CONTAINER** objects | Same locks as exits; hold items. |
| **READABLE** objects | Notes, books, scrolls, signs. **Max 500 characters** each. This is where clues live. |
| **SWITCH** objects | Levers, dials, lenses, valves: 2+ named states, transitions can need a code, item or condition, and outcomes can unlock exits or containers or set story flags. |
| **CONSTRUCTABLE** items | Crafted from ≥2 ingredient items; hidden until crafted. |
| **Hidden** NPCs and objects | Revealed by a condition (searching, an event, a script). Good for secret rooms and late reveals. |
| **Combat** | d20 turn-based fights, NPC special attacks, `ATTACK_ON_SIGHT` NPCs, NPCs that attack once a condition holds (e.g. "after the player reads the ledger"). |
| **Scripts** (Event Scripts setting ON) | Triggers on enter/leave scene, pickup, read, equip, unlock, defeat, sequence start/end, every turn, and **interaction** with any object or NPC (inspect, use, push, talk; also fixed objects). They can set variables, move NPCs, lock or unlock exits, hand over items, damage, win or lose. |
| **Sequence scripts** (scripts ON) | Scripts attached to one chapter that only run while it is active, e.g. "inspecting the bomb opens the wire dialog, but only in chapter 3". Write them in the chapter block as `Chapter Script: on interact with BOMB_ID -> <effect>`. |
| **Sequence soft rules** (scripts ON) | A plain-language condition the GM judges ("the player persuades the clerk using his brother's death") + a script the engine runs, with an optional guard and trigger limit. This is how social solutions get real effects. |
| **Choice dialogs** (scripts ON) | A script shows up to 8 fixed answers (NPC conversation, riddle, confession, dilemma). Each answer runs deterministic code; answers can be hidden until a condition holds, and dialogs can chain into conversations. |
| **Variables & flags** | Remember trust, lies told, evidence found, earlier choices, and use them later in guards. |
| **Win / loss** | Narrative conditions plus optional exact guard checks; scripts can trigger either directly. |

**Cannot do (never design around these):**
- Branching or alternative chapter orders, multiple separate storylines, chapter skipping.
- Real-time pressure (seconds or minutes). In-game time only advances on scene or chapter changes. Express urgency with turn counters in variables or story stakes instead.
- Interacting with **decorative objects** (scene dressing, max 7 per scene). They cannot be taken, used or checked.
- Puzzles that need images, audio, maps drawn by the player, spatial or visual inspection, or exact free-text answers typed into chat (the GM judges chat; only lock dialogs and choice dialogs are exact).
- Companions or party mechanics beyond an NPC following the player via scripts; inventory weight; economy or shops with prices.
- Clue text longer than 500 characters in one readable.

If **Event Scripts** are off in the generator settings, soft rules, choice dialogs and triggers are unavailable. Say in the premise which features the design relies on, and remind the user to enable scripts.

---

## 3. Puzzle design: challenging, fair, enforceable

### Banned (trivial or filler) puzzles
- Counting things in a room ("count the torches / pillars / candles", "multiply the statues by the windows").
- Codes written in plain text, or split into fragments that are simply concatenated ("first half: 45, second half: 89").
- "Find the key in the next room", "the NPC just gives you the code when asked".
- Riddles that are unrelated to the story (generic sphinx riddles with no link to the plot).
- Fetch quests without a decision ("bring me 3 herbs").

Put a line in the premise like **"Design rule: no counting puzzles, no plain-text or simply split codes"**. The builder's default prompts like to add counting puzzles to container locks.

### Good puzzle patterns (always tie them to the story)
1. **Cross-referencing evidence**: the answer only appears when two or more clues from different sources are combined. For example, a tide table + a captain's log entry give the date of the wreck, which is the strongbox code. Every clue is a READABLE or NPC statement placed in a *different* scene.
2. **Reading people**: an NPC only helps when the player uses information found elsewhere (their secret, their debt, their dead brother). Implement it as a **soft rule** with a guard on the evidence (`tw.player.has_item('BROTHERS_LETTER')`) so lucky guesses do not count.
3. **Interrogation / confession dialog**: a choice dialog where the correct accusation needs the right evidence. Answer options that require evidence stay hidden until the player has it, wrong accusations cost trust or HP, and lies are remembered in a variable.
4. **Mechanism with meaning**: a SWITCH whose correct state follows from the lore, not from trial and error (the lighthouse lens must be WHITE because ships steer by white; the log shows it was RED on every wreck night). Gate the critical transition with a guard so brute-forcing a lever does not solve the chapter.
5. **Crafting from insight**: a CONSTRUCTABLE item whose recipe has to be deduced (an antidote from the alchemist's notes + an ingredient only the villain uses).
6. **Moral dilemma with consequence**: a choice dialog whose answers set variables that change later chapters (who survives, who helps, which ending text you get), while every branch stays winnable.
7. **Reversal puzzle**: what the player was told is the solution is the trap; the twist reveals the real solution (see below).

Every puzzle needs: a **fair clue trail** (at least 2 hints, at least one of them a READABLE or NPC line), a **deterministic check** (lock code, key item, switch state, guard, dialog answer, soft rule with guard) and **its solution written in the chapter block** so it ends up in the walkthrough. No puzzle may be solvable only by guessing, and none may block the main path without a way back (retry, alternative clue, NPC hint after failure).

---

## 4. Story requirements

- **Premise with stakes**: who the protagonist is, what they want, and what is lost if they fail, personally and not only for the world.
- **Antagonist with a reason**: their motive must make sense in hindsight.
- **A twist (mandatory)**: a reveal in the second half, with at least one full chapter left after it, that **reframes the goal**. It is not just a surprise fact: after the twist, the player wants or needs something different. Proven twist shapes: the client is the culprit; the "monster" is the victim; the protagonist caused the disaster; the artifact being sought is the threat; the ally has been steering you all along.
- **Plant the twist**: at least **two clues before the reveal** that make sense on a second look (a signature on a receipt, an item in the wrong place, an NPC line with a double meaning). Write in the premise where they are planted.
- **Make the twist mechanical**: the reveal must change the game, not only the text. Examples: a trusted NPC becomes hostile (attack trigger after a flag), a safe route gets locked and a new one opens, an item changes meaning (a script swaps it), the win condition changes.
- **Escalation**: every chapter raises the pressure (new danger, a closing window, a personal loss).
- **A climax that uses what the player learned**: the final obstacle is solved with knowledge and items from earlier chapters, not with a new, unrelated puzzle.
- **An ending with consequences**: earlier choices (variables) colour the ending text; optionally also a bad ending (loss condition) and a bittersweet one.

---

## 5. Output format

Deliver one code block, ready to paste:

```text
<Title>

Premise: <world, protagonist, stakes, tone - 4-8 sentences>
Antagonist: <who, motive>
Twist: <the reveal, in which chapter, what it changes mechanically>
Twist clues: <clue 1 (chapter, where)>, <clue 2 (chapter, where)>
Engine features used: <e.g. soft rules, choice dialogs, switches - requires Event Scripts ON>
Design rule: no counting puzzles, no plain-text or simply split codes, every puzzle has a fair clue trail.
Win: <condition>  Loss: <condition>

[Sidequest: ...] <goal, deterministic completion if any>
[Award: ...] <requirement, e.g. "finish without lying to Ines (variable never set)">

[Sequence: 1] <Title>
<What happens and why it matters. The step-by-step solution of this chapter's puzzle(s), naming clues and IDs.>
[Scene: ...] / [NPC: ...] / [Item: ...] / [Readable: ...] / [Mechanism: ...] tags for the entities introduced here, with their IDs.
Soft Rule: <condition the GM judges> -> <deterministic effect>, guard: <evidence check>, once.
Choice Dialog: <who asks what> - options: <A> (<effect>), <B> (<effect>), <C, only if ...> (<effect>).
Required Item: <ITEM_ID>        (or Required Scene / Defeat NPC, or none)
End Condition: <narrative completion>

[Sequence: 2] ...
```

Then add one short line recommending the builder mode:
- **Strict Adherence** when the chapter structure, twist placement and puzzle chain must stay exactly as written (the usual case for a designed twist).
- **Creative Expansion** when the AI may add intermediate chapters and side content.

---

## 6. Design checklist (check every item before answering)

- [ ] Every hard-rule ID is introduced as an entity with exactly that ID, in UPPER_SNAKE_CASE.
- [ ] No prose line inside a chapter starts with `Item:`, `Scene:`, `Condition:` or `Defeat:`.
- [ ] `[Sidequest]` and `[Award]` tags come before `[Sequence: 1]`.
- [ ] No hard rule is already true when its chapter begins.
- [ ] Each chapter has at least one real obstacle, and the whole adventure has at least 3 different puzzle patterns from §3; there are no banned puzzles.
- [ ] Every clue fits in 500 characters, sits in a READABLE or NPC, and the solution is written in the chapter block.
- [ ] Nothing relies on decorative objects, real time, branching chapters or exact chat input.
- [ ] The twist is planted at least twice, revealed after the midpoint with at least one chapter left to play it out, and changes a mechanic or the goal.
- [ ] The climax uses knowledge and items from earlier chapters.
- [ ] Every choice-dialog branch and every failure keeps the adventure winnable (or is an intended game over).
- [ ] At most 15 chapters; chapter count matches the story (usually 4–7).

---

## 7. Example (condensed)

```text
The Salt Ledger

Premise: Marine insurance investigator Ada Krell arrives in the fog-bound harbor town of Saltreach, where four ships have sunk on the same reef in a year. Her firm will pay out a ruinous sum unless she proves sabotage before the cargo ship Margarethe docks tonight - with Ada's younger brother aboard as a deckhand. Tone: maritime noir, cold and tense.
Antagonist: Harbormaster Ines Varga, who hired Ada. She sells salvage from the wrecks to pay off the town's debts and believes she is saving Saltreach.
Twist: In Sequence 4 Ada realizes her client Ines is the wrecker. The goal flips from "find the saboteur" to "stop Ines and save the Margarethe". Ines turns hostile and locks the lighthouse.
Twist clues: (1) Sequence 2: the salvage receipt is signed "I.V."; (2) Sequence 3: Ines's sea-green shawl lies in the lamp room she claims she never enters.
Engine features used: soft rules, choice dialogs, a SWITCH, attack triggers - requires Event Scripts ON.
Design rule: no counting puzzles, no plain-text or simply split codes, every puzzle has a fair clue trail.
Win: the lighthouse lens shines WHITE when the Margarethe arrives and Ines is stopped. Loss: Ada dies, or the Margarethe is wrecked.

[Award: Honest Broker] Finish without ever lying to Ines (lied_to_ines never set).

[Sequence: 1] The Drowned Harbor
Ada must get into the sealed customs house. Clerk Tobin (TOBIN) refuses; his brother drowned in the second wreck. On the beach Ada finds a torn cargo manifest (WRECK_MANIFEST) naming Tobin's brother as crew. Showing it to Tobin and speaking about his brother makes him hand over the customs key.
[Scene: 1] Saltreach Quay (SALTREACH_QUAY) - fog, gulls, a boarded-up customs house.
[Scene: 2] Wreck Beach (WRECK_BEACH) - debris from the sunken ships.
[NPC: 1] Tobin (TOBIN) - grieving clerk, bitter and honest.
[NPC: 2] Ines Varga (INES_VARGA) - warm, efficient harbormaster; hires Ada and asks to be kept informed.
[Item: 1] Torn Manifest (WRECK_MANIFEST) - lists the drowned crew.
[Item: 2] Customs Key (CUSTOMS_KEY)
Soft Rule: Ada confronts Tobin with his brother's death on the manifest -> Tobin gives CUSTOMS_KEY, guard: player has WRECK_MANIFEST, once.
Required Item: CUSTOMS_KEY
End Condition: Tobin trusts Ada and hands over the customs key.

[Sequence: 2] Ledgers of the Dead
The customs strongbox (CUSTOMS_STRONGBOX) holds the salvage records. Its code is the date of the last wreck as day+month (2203). Clues: the tide table (TIDE_TABLE) says the ships sank "on the first spring tide after the equinox"; the harbor log (HARBOR_LOG) lists the spring tides: 7 March, 22 March, 6 April. The first spring tide after the 20 March equinox is 22 March. Inside lies the salvage receipt (SALVAGE_RECEIPT), signed only "I.V.".
[Scene: 3] Customs House (CUSTOMS_HOUSE)
[Readable: 1] Tide Table (TIDE_TABLE) and Harbor Log (HARBOR_LOG).
[Item: 3] Salvage Receipt (SALVAGE_RECEIPT) - huge sums paid "to the harbor fund", signed I.V.
Required Item: SALVAGE_RECEIPT
End Condition: Ada recovers the salvage receipt.

[Sequence: 3] The Red Lamp
At the lighthouse the drunk keeper Bram (BRAM) is suspected. The keeper's logbook (KEEPER_LOG) shows the lens set to RED on every wreck night, although ships steer by white. Choice Dialog: Bram asks why Ada is here - options: "Accuse him of the wrecks" (Bram shuts down, trust -1), "Show the salvage receipt" (only if Ada has SALVAGE_RECEIPT: Bram admits someone else sets the lens and gives the lamp room key LAMP_ROOM_KEY), "Offer him a drink" (Bram rambles; repeats the dialog). In the lamp room Ada finds Ines's shawl (INES_SHAWL).
[Scene: 4] Lighthouse Base (LIGHTHOUSE_BASE)  [Scene: 5] Lamp Room (LAMP_ROOM, locked with LAMP_ROOM_KEY)
[Mechanism: 1] Lamp Lens (LAMP_LENS) - states WHITE / RED / DARK, currently RED.
Required Item: INES_SHAWL
End Condition: Ada learns someone else changes the lens and finds the shawl.

[Sequence: 4] The Client
Twist. When this chapter starts, Ines arrives at the lighthouse. Choice Dialog with Ines: "Say nothing" (Ines sends Ada to the reef - a trap that costs HP - and leaves to lock the lamp room), "Show the receipt and the shawl" (Ines confesses her motive and attacks), "Offer to split the salvage" (Ines pretends to agree, sets lied_to_ines, then attacks when Ada turns away). Every option ends with Ines becoming hostile, and the lamp room exit is locked by a script until she is defeated.
Defeat NPC: INES_VARGA
End Condition: Ines is stopped.

[Sequence: 5] The Margarethe
Ada must set LAMP_LENS to WHITE before the ship arrives. The transition to WHITE is guarded by the lamp room being unlocked again (key taken from Ines). Ending text depends on whether Ada lied to Ines and whether Tobin was told the truth.
End Condition: The lens shines white and the Margarethe passes the reef safely.
```

Recommended mode: **Strict Adherence**, because the twist placement and clue chain must stay exactly as designed.
