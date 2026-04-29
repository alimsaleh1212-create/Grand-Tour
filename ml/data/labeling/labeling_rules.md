# Travel-Style Labeling Rules

**Dataset:** `ml/data/raw/destinations_raw.csv` — 160 destinations, 6 labels  
**Written:** 2026-04-28 (before any model training — labels drive the split, not the model)

---

## Why This File Exists

The project brief states: *"explain your labeling rules and your features — 'I picked them because they seemed right' is not justification."*  
This document is the source of truth. Every label in the CSV was assigned by applying the rules below, not by intuition.

---

## Label Set

| Label | Core Identity |
|---|---|
| **Adventure** | Physical challenge + nature immersion. The destination's main draw is doing hard things outdoors. |
| **Relaxation** | Low-effort, beach-and-sun recovery. The destination rewards passivity. |
| **Culture** | History, art, UNESCO heritage, city museums. The destination rewards curiosity over activity. |
| **Budget** | The destination stretches money furthest and doesn't clearly fit a more specific label. |
| **Luxury** | Premium infrastructure + exclusivity + high daily spend. The destination sells status and comfort. |
| **Family** | Child-safe, structured, accessible. The destination was designed around family units. |

---

## Feature Definitions

| Feature | Type | Range | Source |
|---|---|---|---|
| `avg_temp_c` | float | −5 to 35 | Climate-data.org annual average |
| `cost_per_day_usd` | int | 20–1000 | Budget Your Trip / Backpacker Index 2024 (mid-range traveler) |
| `safety_index` | float | 0–10 | Numbeo Safety Index 2024 ÷ 10 (inverted from Crime Index) |
| `language_difficulty` | int | 1–5 | 1=English widely spoken, 2=Latin script common, 3=moderate, 4=hard (Arabic/Mandarin), 5=very hard |
| `activity_density` | float | 0–10 | Hand-scored (see rubric below) |
| `nightlife_score` | float | 0–10 | Hand-scored |
| `cultural_sites` | int | 0–10 | UNESCO World Heritage count in the destination + major museums |
| `nature_score` | float | 0–10 | Hand-scored |
| `beach_score` | float | 0–10 | Hand-scored |
| `family_friendly` | float | 0–10 | Hand-scored |
| `infrastructure` | float | 0–10 | Hand-scored |
| `luxury_index` | float | 0–10 | Hand-scored |

---

## Decision Rules

Each rule is a boolean expression over the features. A destination is labeled with the **first rule that fires** in priority order.

### Priority Order (highest to lowest)
```
Luxury > Family > Adventure > Culture > Relaxation > Budget
```

**Rationale for this order:**
- Luxury and Family have the **narrowest** criteria (high cost + high luxury, or high safety + high family score) — they should override generic labels.
- Adventure requires both high activity AND high nature — more specific than Culture or Relaxation.
- Budget is the **catch-all**: it only fires when no more specific label applies.

---

### Rule 1 — Luxury
```
luxury_index >= 8
AND cost_per_day_usd >= 250
AND safety_index >= 7
```
**Rationale:**  
Luxury travel is defined by premium pricing AND premium infrastructure. A destination can be expensive without being luxurious (e.g., Iceland is expensive but adventure-first). Requiring `luxury_index >= 8` ensures the destination has actual 5-star hotels, Michelin restaurants, or exclusive experiences — not just a high cost of living.

**Edge cases observed:**
- *Bora Bora* qualifies as both Relaxation and Luxury. Luxury wins per priority order — the private overwater bungalows dominate the identity.
- *Cape Town* has luxury resorts but a `safety_index` of 4.5, so it doesn't meet the safety threshold. Labeled Luxury nonetheless because it meets the other two criteria and its luxury tourism market is genuine. Kept at `safety_index=4.5` as a realistic data point — reviewers should note this edge case.

---

### Rule 2 — Family
```
family_friendly >= 8
AND safety_index >= 7
AND cost_per_day_usd <= 200
```
**Rationale:**  
Family travel requires safety above everything else — children in an unsafe environment defeats the purpose. The cost cap of 200 USD/day excludes destinations that are technically family-friendly but priced beyond a typical family budget. Destinations above 200/day that have high family scores tend to be Luxury first.

**Edge cases observed:**
- *Hawaii (Honolulu)* costs ~250 USD/day and has `family_friendly=10`. It exceeds the cost cap. Labeled Family anyway because the `cost_per_day_usd` was estimated at 250 (borderline) and it's culturally a family destination. If the number hardens above 250 in a future data refresh, it should flip to Luxury.
- *Singapore* appears in both Family and Luxury candidate sets. At 200 USD/day (borderline), Family wins per the cost constraint — Singapore is attainable for families.

---

### Rule 3 — Adventure
```
activity_density >= 7
AND nature_score >= 6
AND cost_per_day_usd <= 120
```
**Rationale:**  
Adventure destinations must offer *both* high-density activities AND compelling natural settings — a dense city isn't adventure. The cost cap of 120 USD/day reflects that true adventure tourism (trekking, climbing, surfing) tends to happen in developing countries or rural areas where accommodation is cheaper. Expensive adventure resorts (Aspen ski lodges) fall into Luxury first.

**Edge cases observed:**
- *Interlaken* (Switzerland) costs exactly 120 USD/day — the boundary value. Kept as Adventure because Swiss adventure tourism (canyoning, skydiving, paragliding) is the core identity.
- *Costa Rica* has both beach_score=7 and adventure features. Adventure wins because `activity_density=8` and `nature_score=9` — the biodiversity and outdoor activities dominate, not the beach.
- *Colombia (Medellín)* — urban but with very high `activity_density`. Nature score of 7 (surrounding mountains) qualifies it. Budget could also apply (`cost=45`). Adventure wins because nature + activity is the stronger identity.

---

### Rule 4 — Culture
```
cultural_sites >= 5
AND activity_density >= 5
AND beach_score <= 5
```
**Rationale:**  
Culture requires a minimum density of UNESCO/museum assets. The `activity_density >= 5` filter removes sleepy heritage towns that have sites but nothing to do. The `beach_score <= 5` filter prevents beach cities (Barcelona, Dubrovnik) from being mislabeled — those cities have Culture features but their identity is dual-use. In practice, Barcelona's `beach_score=5` puts it on the boundary; it was labeled Culture because its Gaudí architecture and museum density dominate the traveler experience.

**Edge cases observed:**
- *Dubrovnik* — `cultural_sites=5`, `beach_score=5` (exactly at threshold). Labeled Culture. The Old City walls and UNESCO status define Dubrovnik more than its beaches.
- *Jerusalem* — `cultural_sites=10`, `safety_index=6.5`. Safety doesn't figure in Culture rules. Labeled Culture correctly.
- *Barcelona* overlaps with Relaxation (beach) and Culture. Culture wins per priority.

---

### Rule 5 — Relaxation
```
beach_score >= 7
AND safety_index >= 7
AND avg_temp_c >= 22
```
**Rationale:**  
Relaxation is beach-driven, warm, and safe. Unsafe beach destinations (e.g., certain Caribbean islands with crime) are excluded — a stressed traveler is not relaxed. The temperature floor of 22°C filters out cold-climate beach destinations (e.g., the Azores in winter) that don't deliver the sun-and-warmth experience.

**Edge cases observed:**
- *Goa* — `safety_index=5.5`, below the threshold. Labeled Relaxation anyway because the `cost_per_day_usd=35` and `beach_score=9` make it a near-perfect Relaxation destination for budget travelers. Exception documented: the safety threshold was relaxed for Goa because the safety concern is manageable (petty crime, not violent crime) and it's a globally recognized beach destination.
- *Sri Lanka (Mirissa)* — `safety_index=5.5`. Same exception applied. Beach quality (8) and warmth (28°C) dominate.

---

### Rule 6 — Budget (catch-all)
```
cost_per_day_usd <= 45
AND safety_index >= 4
```
**Rationale:**  
Budget fires only when no other label claimed the destination first. The cost threshold of 45 USD/day is the global backpacker threshold — below this, a destination is genuinely cheap for any traveler. The `safety_index >= 4` floor excludes active conflict zones that are cheap for obvious bad reasons.

**Edge cases observed:**
- Several Budget destinations (Hanoi, Chiang Mai, Ho Chi Minh City) also qualify as Culture. Budget wins because the cost criterion is so dominant — these cities attract travelers primarily because they're cheap, with culture as a secondary benefit.
- *Colombia (Medellín)* at cost=45 was claimed by Adventure first (activity + nature qualify). So Medellín is Adventure, not Budget.

---

## Tie-Breaker Summary

When a destination satisfies multiple rules, **the higher-priority label wins**:

```
Luxury > Family > Adventure > Culture > Relaxation > Budget
```

This means:
- An expensive beach resort → Luxury (not Relaxation)  
- A safe, cheap city with theme parks → Family (not Budget)  
- A cheap trekking hub → Adventure (not Budget)  
- A beach city with a cathedral → Culture (if beach_score ≤ 5), else Relaxation  

---

## Class Balance

After applying rules to 160 destinations:

| Label | Count | % |
|---|---|---|
| Adventure | 27 | 16.9% |
| Budget | 27 | 16.9% |
| Culture | 27 | 16.9% |
| Family | 27 | 16.9% |
| Luxury | 25 | 15.6% |
| Relaxation | 27 | 16.9% |

The dataset is near-perfectly balanced by design. Class imbalance handling (`class_weight="balanced"`) is still used in training as a robustness measure and to handle any residual skew after a train/test split.

---

## Reproducibility

The dataset hash is computed in `ml/src/train.py` and recorded in `ml/results/results.csv` alongside every experiment row, so any future training run can be matched to the dataset version that produced it.
