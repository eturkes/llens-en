---
name: vancomycin-tdm
description: "Workflow for AUC24 estimation, concentration-time curve visualization, and dose adjustment suggestions in vancomycin therapeutic drug monitoring (TDM). Activate when the user consults about 'vancomycin TDM,' 'vanco levels,' 'peak/trough,' 'AUC24,' 'what dose of vanco should I use,' etc. Does not use tools; performs calculation and plotting via Pyodide (Code Interpreter). At Hokkaido University Hospital, the pharmacy department's TDM support service is the standard point of contact, and this SKILL is positioned as an aid for initial assessment, education, and what-if exploration."
---

# Vancomycin TDM Workflow

## Positioning

At Hokkaido University Hospital, the pharmacy department's TDM support service is the standard point of contact. This SKILL is for the following supplementary purposes:

- When the user (physician) wants a quick **initial assessment** of AUC24
- When viewing concentration-time curves for **educational purposes**
- When trying **what-if** scenarios for dose changes

Always note at the end of the response that for higher-accuracy predictions (Bayesian estimation, population PK models) or formal dosing recommendations, consultation with the pharmacy department's TDM support service is recommended.

## Workflow

### Step 1: Gathering Required Information

Confirm the following in order. **Do not ask for everything at once** (physicians dislike being overwhelmed with information requests). Items already provided may be skipped.

**Minimum required information**:
1. Lab values: Peak concentration (mg/L), Trough concentration (mg/L)
2. Sampling timing:
   - Which dose number the sampling was performed on (steady state = 4th dose or later is preferred)
   - Peak sampling: How many hours after end of infusion (typically 1 hour)
   - Trough sampling: How many hours before the next dose (typically immediately before or 30 minutes before)
3. Current regimen: Single dose (mg), dosing interval (hours), infusion duration (typically 1 hour)

**Desirable additional information** (improves dosing recommendation accuracy):
4. Patient background: Weight, age, sex, Cr (eGFR)
5. Indication: MRSA bacteremia? Meningitis? etc. (target AUC24 may differ)
6. MIC value if available (assume MIC = 1 mg/L if unavailable)

### Step 2: Calculation (Execute in Pyodide)

Execute the following Python code in the Code Interpreter.

```python
import math
import matplotlib.pyplot as plt
import numpy as np
import io, base64

# ===== Input (replace with gathered values) =====
trough_mg_l = 15.0       # Trough concentration (mg/L)
peak_mg_l = 30.0         # Peak concentration (mg/L)
dose_mg = 1000           # Single dose (mg)
dosing_interval_h = 12   # Dosing interval (h)
infusion_duration_h = 1.0
time_peak_after_infusion_end_h = 1.0   # Time from end of infusion to peak sampling
time_trough_before_next_dose_h = 0.5   # Time before next dose for trough sampling
mic_mg_l = 1.0           # MIC (assume 1.0 if unknown)

# ===== One-compartment model PK parameter estimation =====
# Elapsed time between samplings
t_peak = infusion_duration_h + time_peak_after_infusion_end_h
t_trough = dosing_interval_h - time_trough_before_next_dose_h
delta_t = t_trough - t_peak

if peak_mg_l <= trough_mg_l:
    raise ValueError("Peak concentration is less than or equal to trough concentration. Please verify sampling times.")
if delta_t <= 0:
    raise ValueError("Sampling times are contradictory.")

# Elimination rate constant ke, half-life
ke = math.log(peak_mg_l / trough_mg_l) / delta_t
half_life = math.log(2) / ke

# Extrapolate true Cmax (at end of infusion) and Cmin (immediately before next dose)
c_max_true = peak_mg_l * math.exp(ke * time_peak_after_infusion_end_h)
c_min_true = trough_mg_l * math.exp(-ke * time_trough_before_next_dose_h)

# AUC_tau (AUC for one dosing interval)
# During infusion: Linear rise from 0 to c_max_true (approximation)
# Elimination phase: Exponential decay from c_max_true to c_min_true
auc_infusion_phase = infusion_duration_h * c_max_true / 2
auc_elim_phase = (c_max_true - c_min_true) / ke
auc_tau = auc_infusion_phase + auc_elim_phase
auc24 = auc_tau * (24 / dosing_interval_h)

# AUC24/MIC
auc_mic_ratio = auc24 / mic_mg_l

# ===== Assessment =====
if auc_mic_ratio < 400:
    assessment = "subtherapeutic"
    recommendation = "Consider dose increase (consultation with TDM support service recommended)"
elif auc_mic_ratio <= 600:
    assessment = "therapeutic"
    recommendation = "Continue current dose"
else:
    assessment = "potentially toxic"
    recommendation = "Nephrotoxicity risk, consider dose reduction (consultation with TDM support service recommended)"

print(f"=== Pharmacokinetic Parameters ===")
print(f"Elimination rate constant ke = {ke:.4f} /h")
print(f"Half-life = {half_life:.2f} h")
print(f"Extrapolated Cmax (at end of infusion) = {c_max_true:.2f} mg/L")
print(f"Extrapolated Cmin (immediately before next dose) = {c_min_true:.2f} mg/L")
print(f"")
print(f"=== AUC Assessment ===")
print(f"AUC_tau (one dosing interval) = {auc_tau:.1f} mg*h/L")
print(f"AUC24 = {auc24:.1f} mg*h/L")
print(f"AUC24/MIC = {auc_mic_ratio:.0f} (assuming MIC={mic_mg_l} mg/L)")
print(f"Assessment: {assessment}")
print(f"Recommendation: {recommendation}")

# ===== Plot =====
plt.figure(figsize=(10, 6))

# Concentration-time curve for one dosing interval
t_inf = np.linspace(0, infusion_duration_h, 50)
c_inf = c_max_true * (t_inf / infusion_duration_h)  # Linear approximation during infusion
t_elim = np.linspace(infusion_duration_h, dosing_interval_h, 200)
c_elim = c_max_true * np.exp(-ke * (t_elim - infusion_duration_h))

t_all = np.concatenate([t_inf, t_elim])
c_all = np.concatenate([c_inf, c_elim])
plt.plot(t_all, c_all, 'b-', linewidth=2, label='Predicted concentration')

# Target range (approximate mean concentration for AUC24 400-600: 16.7-25 mg/L)
plt.axhspan(400/24, 600/24, alpha=0.2, color='green', label=f'Target Cavg ({400/24:.1f}-{600/24:.1f} mg/L for AUC24 400-600)')

# Sampling points
plt.plot(t_peak, peak_mg_l, 'ro', markersize=10, label=f'Peak measured: {peak_mg_l} mg/L')
plt.plot(t_trough, trough_mg_l, 'go', markersize=10, label=f'Trough measured: {trough_mg_l} mg/L')

# Extrapolated points
plt.plot(infusion_duration_h, c_max_true, 'r^', markersize=8, alpha=0.5, label=f'Cmax extrapolated: {c_max_true:.1f}')
plt.plot(dosing_interval_h, c_min_true, 'g^', markersize=8, alpha=0.5, label=f'Cmin extrapolated: {c_min_true:.1f}')

plt.xlabel('Time after dose start (hours)')
plt.ylabel('Concentration (mg/L)')
plt.title(f'Vancomycin concentration-time curve\n'
          f'{dose_mg} mg q{int(dosing_interval_h)}h | AUC24 = {auc24:.0f} mg*h/L | t1/2 = {half_life:.1f} h | {assessment}')
plt.legend(loc='upper right', fontsize=9)
plt.grid(True, alpha=0.3)
plt.xlim(0, dosing_interval_h)
plt.ylim(0, max(c_max_true, peak_mg_l) * 1.2)

# Output as base64 per OpenWebUI display rules
buf = io.BytesIO()
plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
buf.seek(0)
print(f"data:image/png;base64,{base64.b64encode(buf.read()).decode()}")
plt.close()
```

### Step 3: Interpretation and Presentation of Results

1. **Present numerical results in a table**: AUC24, half-life, extrapolated Cmax/Cmin, assessment
2. **Concentration-time curve**: Display the plot
3. **Clinical interpretation**:
   - Position relative to the target range (AUC24 400-600)
   - Appropriateness of the dosing interval based on half-life (2-3 times the half-life is a standard dosing interval)
   - If out of range, briefly suggest the direction (whether dose change or interval change is more appropriate)
4. **Referral to pharmacy department TDM support**: Recommend consultation with the pharmacy department's TDM support service when implementing dose changes

### Step 4: What-if Exploration (When Requested)

When the user asks "What if the dose were 1.5g?" or "What if we shortened to q8h?", edit the Step 2 code and re-execute. Pyodide allows unlimited iterations.

Prediction formulas for what-if scenarios:
- Assume the same patient's ke and Vd remain unchanged (already estimated)
- Enter the new dose and interval to calculate a new AUC24
- Use ke and Vd from the previous calculation results

```python
# Reuse ke from previous calculation, predict with new regimen
new_dose = 1500
new_interval = 12

# Estimate Vd (simplified): Vd = Dose / [ke * infusion_duration * Cmax_true * (1 - e^(-ke*infusion))]
# More precisely: AUC_tau = Dose / CL, CL = ke * Vd
cl = dose_mg / auc_tau   # Back-calculate CL from known regimen
new_auc_tau = new_dose / cl
new_auc24 = new_auc_tau * (24 / new_interval)
print(f"What-if: {new_dose}mg q{new_interval}h -> AUC24 approx {new_auc24:.0f} mg*h/L")
```

## Cautions

### Required Disclaimers

Always append the following at the end of the response:

1. **This value is a simplified estimate using the two-point sampling method** and is less accurate than Bayesian estimation (PrecisePK, etc.)
2. **Assumes sampling at steady state (typically 4th dose or later)**. Estimates will deviate significantly with earlier data
3. **Evaluated assuming MIC = 1 mg/L**. For MRSA with MIC >= 2, the target AUC24 also increases
4. **Consultation with the pharmacy department's TDM support service is recommended** for formal dose changes

### Pitfalls

- **Contradictory sampling times**: Peak sampling too soon after infusion end, trough sampling too far from the next dose, etc. are sources of estimation error. Confirm sampling times with the user
- **Rapid changes in renal function**: The calculation reflects the state at the time of sampling, but predictions may not hold for patients with rapidly changing renal function. Confirm Cr trends with the user
- **Continuous vs. intermittent infusion**: This SKILL assumes intermittent infusion (q8h, q12h, etc.). Continuous infusion requires different equations
- **Pediatric, pregnant, or dialysis patients**: The equations in this SKILL assume adult, non-dialysis patients. Pharmacy department TDM is required for these populations

### Dose Adjustment Principles (General)

- AUC24 < 400: Prioritize dose increase (over interval shortening)
- AUC24 > 600 + high trough: Prioritize interval extension
- AUC24 > 600 + normal trough + high Cmax: Reduce single dose
- Half-life < 4h: Consider shortening the dosing interval (consider q8h)
- Half-life > 12h: Consider extending the dosing interval (consider q24h), verify renal function

However, **definitive dosing decisions are deferred to the Hokkaido University Hospital pharmacy department TDM support**. This SKILL provides directional guidance only.

## Hokkaido University Hospital Pharmacy Department

- Extension: 5685

## Other Feedback

- Email: prism-hu-office@pop.med.hokudai.ac.jp
- Extension: 5352
