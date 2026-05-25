---
name: medical-calculator
description: "A collection of medical calculation and scoring tools (`calc_*`) frequently used in clinical practice. Provides 10 functions: eGFR, CCr, MELD-Na, ALBI, FIB-4, APACHE II, Glasgow-Blatchford, Ranson, DIC (ISTH/JMHW), and integrated acid-base analysis. When a calculation or scoring is needed during a consultation with a user, always use these tools rather than performing mental arithmetic. Simple formulas such as BMI, BSA, corrected Ca, and A-aDO2 are not included in this tool set (calculate using internal arithmetic)."
---

# Medical Calculator (`calc_*`)

## When to Use

When the following calculations or scoring are needed during a conversation with a physician. **Always call the tool rather than performing mental arithmetic**. This set contains formulas where branching logic and threshold decisions are complex and prone to error when done mentally.

| Domain | Function | Purpose |
|------|------|------|
| Renal | `calc_egfr_ckdepi2021` | eGFR (CKD-EPI 2021) |
| Renal | `calc_egfr_jsn` | eGFR (Japanese Society of Nephrology 2009, domestic standard) |
| Renal | `calc_ccr_cockcroft_gault` | CCr (drug dosage adjustment) |
| Renal | `calc_free_water_deficit` | Free water deficit (hypernatremia) |
| Hepatic | `calc_meld_na` | MELD-Na (transplant eligibility, etc.) |
| Hepatic | `calc_albi_grade` | ALBI grade (prognosis in HCC, etc.) |
| Hepatic | `calc_fib4` | FIB-4 (fibrosis screening in chronic hepatitis) |
| ICU/Emergency | `calc_apache2` | APACHE II (severity) |
| ICU/Emergency | `calc_sofa` | SOFA (Sepsis-3 sepsis diagnosis, serial organ dysfunction assessment) |
| Gastroenterology | `calc_glasgow_blatchford` | GBS (upper GI bleeding risk) |
| Gastroenterology | `calc_ranson_criteria` | Ranson (acute pancreatitis severity) |
| Hematology | `calc_dic_score` | DIC (ISTH overt / JMHW) |
| Blood Gas | `calc_acid_base_analysis` | Integrated acid-base analysis (primary + compensation + AG) |

## Not Included (Calculate Using Internal Arithmetic)

The following are not included in this tool set as they can be done with simple formulas:

- **Body metrics**: BMI, BSA (Du Bois / Mosteller), IBW (Devine)
- **Electrolyte corrections**: Corrected Ca (Payne), corrected Na, free water deficit
- **Oxygenation**: A-aDO2, P/F ratio
- **Additive scores**: CHA2DS2-VASc, HAS-BLED, Wells, **qSOFA**, CURB-65, NEWS2, Child-Pugh, GCS
- **Other**: Anion gap alone, HbA1c to eAG conversion, Holliday-Segar fluid calculation

These can be accurately calculated using the internal arithmetic module when the formula and input values are available.

## Common Input Unit Rules

If the user's input units differ from these, **convert before passing to the tool** (the tools are implemented to accept the units below).

| Item | Unit |
|------|------|
| Creatinine (Cr) | mg/dL |
| Bilirubin | mg/dL |
| Albumin | g/dL |
| Na, K, Cl | mEq/L |
| Ca | mg/dL |
| BUN | mg/dL |
| Blood glucose | mg/dL |
| Platelets | **x10^4/uL (Japanese notation)** |
| WBC | **x10^3/uL** |
| Hb, Hct | g/dL, % |
| Body weight | kg |
| Body temperature | degrees C |
| Blood gas (PaO2, PaCO2) | mmHg |
| HCO3 | mEq/L |
| AST, ALT, LDH | U/L |
| FDP, D-dimer | ug/mL |

In particular, **platelet units** are accepted in **Japanese clinical notation (x10^4/uL)**, not the international standard (x10^9/L). If the user says "platelets 80,000," pass `8.0`.

## Usage and Tips for Each Function

### `calc_egfr_ckdepi2021`

eGFR using the CKD-EPI 2021 (race-free) equation. Includes CKD stage determination.

- Set `japanese_coefficient=True` to apply the Japanese correction factor (x0.813)
- The standard at Hokkaido University Hospital requires confirmation (default is `False`)
- **For drug dosage adjustment, use `calc_ccr_cockcroft_gault` instead of this value** (eGFR is a body surface area-adjusted relative value; pharmacokinetics require absolute values)

### `calc_egfr_jsn`

eGFR using the Japanese Society of Nephrology 2009 estimation formula. **This formula is widely used domestically**, so when a user simply says "eGFR," choosing this over CKD-EPI is traditionally more appropriate in many cases.

- Assumes enzymatic Cr (Jaffe method is not suitable)
- Values differ slightly from CKD-EPI 2021. Presenting both is also acceptable
- Same as other eGFR equations: use Cockcroft-Gault for drug dosage adjustment

### `calc_ccr_cockcroft_gault`

CCr (absolute value) for drug dosage adjustment.

- Actual body weight is typically used, but **for obese patients (BMI >= 30), recalculation using IBW or AdjBW is recommended**. Inform the user accordingly and, if needed, calculate IBW internally before passing
- IBW may be safer even in lean patients for certain drugs (aminoglycosides, etc.)

### `calc_free_water_deficit`

Free water deficit in hypernatremia.

- **Returns an error when Na <= target Na (default 140)** (no deficit)
- For ages 65 and above, the TBW ratio decreases (male 0.6 to 0.5, female 0.5 to 0.45), so always pass age
- The return value `suggested_24h_volume_L` **assumes chronic hypernatremia and proposes half of the total deficit** (for acute cases the full amount may be corrected; for chronic cases, gradual correction to avoid osmotic demyelination risk)
- Acute/chronic differentiation is left to the user's clinical judgment. This function only calculates
- When selecting IV fluids, note the free water content of each solution (5% dextrose = 100%, half-normal saline = 50%, normal saline = 0%)

### `calc_meld_na`

UNOS 2016 MELD-Na formula. Supports dialysis adjustment (2 or more sessions within the past 7 days or 24h CRRT).

- Bilirubin/INR/Cr values below 1.0 are clipped to 1.0 (formula specification)
- Na is clipped to 125-137
- **When MELD <= 11, MELD-Na = MELD** (formula specification)
- MELD 3.0 (2023 onward) is not implemented. Specify if the latest version is needed

### `calc_albi_grade`

Hepatic reserve assessment (frequently used in HCC, etc.).

- Input units are accepted in **g/dL and mg/dL** (internally converted to umol/L and g/L)
- Returns Grade 1 (best) / 2 (intermediate) / 3 (worst)

### `calc_fib4`

Fibrosis screening for chronic hepatitis (HCV/HBV/NAFLD).

- **Do not apply to acute liver injury** (FIB-4 is falsely elevated when AST rises significantly in acute inflammation)
- Thresholds differ for patients under vs. 65 and older (auto-switched per NAFLD guideline compliance)

### `calc_apache2`

Calculate using the **worst values** within 24 hours of ICU admission.

- Oxygenation score: **pass A-aDO2 when FiO2 >= 0.5, or PaO2 when FiO2 < 0.5**. Error if both are None
- Substituting HCO3 for pH in the score is not implemented (prioritize pH if arterial blood gas is available)
- `chronic_organ_failure` indicates severe chronic organ failure or immunocompromised status (dialysis patients, Child-C cirrhosis, chronic respiratory failure with O2 dependence, on chemotherapy, etc.)
- **Does not return estimated mortality** (requires disease category-specific coefficient tables). Present the score only and defer judgment to the attending physician

### `calc_sofa`

Used for Sepsis-3 sepsis diagnosis (infection + acute SOFA increase >= 2 points) and serial organ dysfunction assessment in the ICU. **The large number of input items makes manual calculation cumbersome in practice, giving high value to tool-based calculation**.

- 6 organs (respiration, coagulation, hepatic, cardiovascular, CNS, renal) each scored 0-4, total 0-24
- **Missing items are excluded from the score and returned as None**. When not all items are available, inform the user and encourage recalculation after completion
- Respiratory score changes at P/F < 200 depending on mechanical ventilation status (always specify `mechanical_ventilation`)
- Cardiovascular score is determined by vasopressor type and dose. `vasopressor` options:
  - `none`: No vasopressors; MAP < 70 = 1 point, >= 70 = 0 points
  - `dopamine_low`: Dopamine <= 5 ug/kg/min or dobutamine only = 2 points
  - `dopamine_mid`: Dopamine 5.1-15 or norepinephrine/epinephrine <= 0.1 = 3 points
  - `dopamine_high`: Dopamine > 15 or norepinephrine/epinephrine > 0.1 = 4 points
- Renal score is determined separately by Cr and urine output, **the higher score is adopted** (if only one is available, it is used)
- For serial assessment, the change from baseline (delta-SOFA) is important. It may be useful to ask the user "Is this the initial assessment or a follow-up?"
- qSOFA (simple addition of 3 items) is not included in this tool set. Use the arithmetic module

### `calc_glasgow_blatchford`

Risk stratification for upper GI bleeding (pre-endoscopy triage).

- **GBS = 0 is a candidate for outpatient management**; GBS >= 7 often requires intervention
- BUN and sex-specific Hb thresholds are key to scoring, so ask the user if they have not been provided

### `calc_ranson_criteria`

Acute pancreatitis severity. **Call separately for the 5 admission items and 6 items at 48 hours** (`timing="admission"` or `"48h"`).

- A combined score of admission + 48-hour >= 3 suggests severe pancreatitis
- Thresholds differ for gallstone pancreatitis (`gallstone_etiology=True`)
- **In Japan, JSS-CT grade / JMHW severity criteria are the standard**. Inform the user that Ranson originated in the West

### `calc_dic_score`

Select from three criteria:

- `criteria="isth_overt"`: ISTH overt DIC (international standard, >= 5 for DIC)
- `criteria="jmhw_hematologic"`: JMHW hematologic type (>= 4, for leukemia, etc.)
- `criteria="jmhw_non_hematologic"`: JMHW non-hematologic type (>= 7)

How to choose:

- For **hematologic malignancies/hematopoietic disorders** such as leukemia, myelodysplastic syndrome, or post-chemotherapy bone marrow suppression: `jmhw_hematologic`
- For other cases when **domestic criteria are requested**: `jmhw_non_hematologic`
- For **international comparison or publication purposes**: `isth_overt`

The ISTH fibrin marker threshold is simplified in the implementation (>= 25 = 3 points, >= 5 = 2 points). Since cutoffs vary by facility's FDP kit, alert the user in borderline cases.

### `calc_acid_base_analysis`

Integrated analysis of blood gas. Performs primary disorder determination + compensation prediction + AG calculation in one call.

- pH, pCO2, HCO3 are required
- If Na and Cl are available, AG is calculated
- If albumin (g/dL) is available, corrected AG is also calculated (detects high AG masked by hypoalbuminemia)
- If the return value `compensation_status` is anything other than `appropriate_compensation`, present the possibility of a mixed disorder

## Handling Return Values

Each function **returns a dictionary** (acid-base returns a compound structure). Interpretation and threshold information for each value are included in the return value, so no additional mental arithmetic is needed.

Example presentation to the user:

> eGFR (CKD-EPI 2021) is **67.1 mL/min/1.73m2**, CKD stage G2.
> With the Japanese correction factor applied, it is 54.6 mL/min/1.73m2 (G3a).
> If the purpose is drug dosage adjustment, please also check CCr (absolute value) via Cockcroft-Gault.

## Pitfalls and Cautions

1. **Unit mix-up**: Strictly follow the unit rules table above. If the user provides values in different units, convert before passing
2. **Off-label use**: Do not use FIB-4 for acute hepatitis, Ranson for chronic pancreatitis, etc.
3. **Coexistence of multiple formulas**: Multiple eGFR formulas coexist (CKD-EPI 2021 / JSN / MDRD, etc.). Follow the facility standard if established; otherwise, confirm with the user
4. **Scores are only one input for decision-making**: Do not state definitively, e.g., "APACHE II 19 means X% mortality." Encourage the attending physician's comprehensive judgment
5. **When the user provides only approximate values**: Do not rely on mental arithmetic; always pass values to the tool and present the result. However, note in the presentation that input values were approximate

## Related SKILL

Calculation-related items not covered by this SKILL that are implemented as separate SKILLs:

- **`vancomycin-tdm`**: Vancomycin TDM. Performs history gathering, AUC24 calculation, concentration-time curve plotting, and dose adjustment suggestions via a Pyodide workflow. Its distinguishing feature is direct calculation and plotting in Pyodide rather than using tools
- (Aminoglycoside TDM, antiepileptic drug TDM, etc. are planned for addition in the same pattern)

## Extension Candidates (Not Implemented)

The following are not included in this implementation. Relay to the development team if requested by users:

- GRACE, TIMI, PESI/sPESI, BISAP
- Calvert formula (carboplatin AUC)
- MELD 3.0 (UNOS 2023 onward)
- Na correction rate upper limit warning

## Feedback

If `calc_*` output seems off, thresholds do not match the facility standard, or additional calculations are desired, contact the development team:

- Email: prism-hu-office@pop.med.hokudai.ac.jp
- Extension: 5352
