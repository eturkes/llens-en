"""
title: Medical Calculator
author: Ken Enda
version: 0.1
description: Medical calculation and scoring tools frequently used in clinical practice
             that are cumbersome and error-prone when done by hand.
             Refer to the SKILL side for detailed usage instructions.
requirements:
"""

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class Tools:
    """Medical calculation tool collection. All prefixed with `calc_`.

    Scope: Only calculations where arithmetic modules alone lack precision,
    or where formula branching and threshold logic make manual computation
    error-prone. Simple formulas like BMI / BSA / corrected Ca / A-aDO2
    are not included here (model-side arithmetic is sufficient).
    """

    class Valves(BaseModel):
        # No external dependencies at present. Reserved for future reference range
        # or institution-specific formula substitution.
        institution_egfr_default: str = Field(
            default="ckdepi_2021",
            description="Default eGFR formula (ckdepi_2021 / jsn / mdrd)",
        )

    def __init__(self) -> None:
        self.valves = self.Valves()

    # =========================================================================
    # Renal function
    # =========================================================================

    def calc_egfr_ckdepi2021(
        self,
        cr: float,
        age: int,
        sex: Literal["M", "F"],
        japanese_coefficient: bool = False,
    ) -> Dict[str, Any]:
        """Calculate eGFR using the CKD-EPI 2021 equation (mL/min/1.73m2).

        :param cr: Serum creatinine (mg/dL)
        :param age: Age (years)
        :param sex: "M" or "F"
        :param japanese_coefficient: Whether to apply the Japanese coefficient (x0.813)
        :return: {egfr, formula, japanese_coefficient_applied, ckd_stage}
        """
        # CKD-EPI 2021 (race-free)
        if sex == "F":
            kappa, alpha, sex_factor = 0.7, -0.241, 1.012
        else:
            kappa, alpha, sex_factor = 0.9, -0.302, 1.0
        ratio = cr / kappa
        egfr = (
            142
            * (min(ratio, 1) ** alpha)
            * (max(ratio, 1) ** -1.200)
            * (0.9938 ** age)
            * sex_factor
        )
        if japanese_coefficient:
            egfr *= 0.813

        # CKD stage classification
        if egfr >= 90:
            stage = "G1"
        elif egfr >= 60:
            stage = "G2"
        elif egfr >= 45:
            stage = "G3a"
        elif egfr >= 30:
            stage = "G3b"
        elif egfr >= 15:
            stage = "G4"
        else:
            stage = "G5"

        return {
            "egfr": round(egfr, 1),
            "unit": "mL/min/1.73m2",
            "formula": "CKD-EPI 2021 (race-free)",
            "japanese_coefficient_applied": japanese_coefficient,
            "ckd_stage": stage,
        }

    def calc_ccr_cockcroft_gault(
        self,
        cr: float,
        age: int,
        sex: Literal["M", "F"],
        weight_kg: float,
    ) -> Dict[str, Any]:
        """Calculate creatinine clearance (mL/min) using the Cockcroft-Gault equation.
        Used for drug dosage adjustment. No body surface area correction (absolute value).

        :param cr: Serum creatinine (mg/dL)
        :param age: Age (years)
        :param sex: "M" or "F"
        :param weight_kg: Body weight (kg). Consider using IBW or AdjBW for obese patients.
        :return: {ccr, unit, formula, note}
        """
        ccr = ((140 - age) * weight_kg) / (72 * cr)
        if sex == "F":
            ccr *= 0.85
        return {
            "ccr": round(ccr, 1),
            "unit": "mL/min",
            "formula": "Cockcroft-Gault",
            "note": (
                "No body surface area correction. Use this value for drug dosage adjustment. "
                "For obese patients (BMI>=30), consider recalculating with IBW or AdjBW "
                "instead of actual body weight."
            ),
        }

    # =========================================================================
    # Hepatic
    # =========================================================================

    def calc_meld_na(
        self,
        bilirubin: float,
        cr: float,
        inr: float,
        na: float,
        dialysis_2x_in_last_week: bool = False,
    ) -> Dict[str, Any]:
        """Calculate MELD-Na score (for transplant eligibility evaluation, etc.).

        :param bilirubin: Total bilirubin (mg/dL)
        :param cr: Serum creatinine (mg/dL). Clipped to 4.0 for dialysis patients.
        :param inr: PT-INR
        :param na: Serum Na (mEq/L). Clipped to 125-137 range.
        :param dialysis_2x_in_last_week: 2 or more dialysis sessions or 24h CRRT in past 7 days
        :return: {meld, meld_na, components}
        """
        import math

        # Lower bound clipping (values below 1.0 are treated as 1.0)
        bili = max(bilirubin, 1.0)
        inr_c = max(inr, 1.0)
        cr_c = max(cr, 1.0)
        if dialysis_2x_in_last_week or cr >= 4.0:
            cr_c = 4.0

        meld = (
            0.957 * math.log(cr_c)
            + 0.378 * math.log(bili)
            + 1.120 * math.log(inr_c)
            + 0.643
        ) * 10
        meld = round(meld)
        meld = max(6, min(meld, 40))

        # MELD-Na (UNOS 2016 formula)
        na_c = max(125, min(na, 137))
        if meld > 11:
            meld_na = meld + 1.32 * (137 - na_c) - (0.033 * meld * (137 - na_c))
            meld_na = round(meld_na)
            meld_na = max(6, min(meld_na, 40))
        else:
            meld_na = meld

        return {
            "meld": meld,
            "meld_na": meld_na,
            "components": {
                "bilirubin_used": bili,
                "cr_used": cr_c,
                "inr_used": inr_c,
                "na_used": na_c,
                "dialysis_adjustment_applied": dialysis_2x_in_last_week or cr >= 4.0,
            },
            "note": "UNOS 2016 MELD-Na formula. When MELD<=11, MELD-Na equals MELD.",
        }

    def calc_albi_grade(
        self,
        albumin_g_dl: float,
        bilirubin_mg_dl: float,
    ) -> Dict[str, Any]:
        """Calculate ALBI score / grade (hepatic reserve assessment, frequently used in HCC, etc.).

        :param albumin_g_dl: Albumin (g/dL)
        :param bilirubin_mg_dl: Total bilirubin (mg/dL)
        :return: {albi_score, albi_grade, note}
        """
        import math

        # ALBI is defined with bilirubin in umol/L and albumin in g/L, so unit conversion is needed
        bili_umol = bilirubin_mg_dl * 17.1
        alb_g_l = albumin_g_dl * 10
        albi = math.log10(bili_umol) * 0.66 + alb_g_l * (-0.085)

        if albi <= -2.60:
            grade = 1
        elif albi <= -1.39:
            grade = 2
        else:
            grade = 3

        return {
            "albi_score": round(albi, 3),
            "albi_grade": grade,
            "note": (
                "Grade 1: Best (median OS 18.5-85.6 months), "
                "Grade 2: Intermediate, "
                "Grade 3: Worst (median OS 5.3-6.2 months)."
            ),
        }

    def calc_fib4(
        self,
        ast: float,
        alt: float,
        plt_10e4_per_ul: float,
        age: int,
    ) -> Dict[str, Any]:
        """Calculate FIB-4 index (fibrosis screening for chronic liver disease).

        :param ast: AST (U/L)
        :param alt: ALT (U/L). Must not be 0.
        :param plt_10e4_per_ul: Platelet count (x10^4/uL, Japanese notation).
        :param age: Age (years)
        :return: {fib4, interpretation, note}

        Note: For fibrosis screening in chronic hepatitis (HCV/HBV/NAFLD).
              Not applicable to acute liver injury.
        """
        import math

        # Japanese notation (x10^4/uL) to US notation (x10^9/L) is equivalent
        # (x10^4/uL = x10/nL = x10^9/L*0.01)
        # FIB-4 denominator is defined as PLT(x10^9/L). 1x10^4/uL = 10x10^9/L -> x10
        plt_10e9_l = plt_10e4_per_ul * 10
        if plt_10e9_l == 0 or alt <= 0:
            return {"error": "PLT and ALT must be positive values"}

        fib4 = (age * ast) / (plt_10e9_l * math.sqrt(alt))

        # Thresholds differ for age <65 vs >=65 (NAFLD)
        if age < 65:
            low, high = 1.30, 2.67
        else:
            low, high = 2.0, 2.67

        if fib4 < low:
            interp = "low_risk (advanced fibrosis unlikely)"
        elif fib4 < high:
            interp = "indeterminate (further evaluation recommended)"
        else:
            interp = "high_risk (advanced fibrosis likely, consider specialist referral)"

        return {
            "fib4": round(fib4, 2),
            "interpretation": interp,
            "thresholds_used": {"low": low, "high": high, "age_group": "<65" if age < 65 else ">=65"},
            "note": "Screening index for chronic hepatitis (HCV/HBV/NAFLD). Not suitable for acute liver injury.",
        }

    # =========================================================================
    # Critical care / Emergency
    # =========================================================================

    def calc_apache2(
        self,
        # APS (Acute Physiology Score) 12 items
        temp_c: float,
        map_mmhg: float,
        hr: int,
        rr: int,
        fio2: float,
        pao2: Optional[float] = None,
        a_ado2: Optional[float] = None,
        ph: float = 7.40,
        na: float = 140,
        k: float = 4.0,
        cr_mg_dl: float = 1.0,
        acute_renal_failure: bool = False,
        hct: float = 40,
        wbc_10e3_ul: float = 8.0,
        gcs: int = 15,
        # Age
        age: int = 50,
        # Chronic disease
        chronic_organ_failure: bool = False,
        admission_type: Literal[
            "non_op", "emergency_post_op", "elective_post_op"
        ] = "non_op",
    ) -> Dict[str, Any]:
        """Calculate APACHE II score (computed from worst values within 24 hours of ICU admission).

        :param temp_c: Temperature (degrees C, rectal is standard)
        :param map_mmhg: Mean arterial pressure (mmHg)
        :param hr: Heart rate (/min)
        :param rr: Respiratory rate (/min)
        :param fio2: Fraction of inspired oxygen (0.21-1.0)
        :param pao2: PaO2 (mmHg). Used when FiO2 < 0.5.
        :param a_ado2: A-aDO2 (mmHg). Used when FiO2 >= 0.5.
        :param ph: Arterial blood pH (this implementation prioritizes pH over HCO3 substitute)
        :param na: Serum Na (mEq/L)
        :param k: Serum K (mEq/L)
        :param cr_mg_dl: Serum Cr (mg/dL)
        :param acute_renal_failure: Acute renal failure (Cr score is doubled)
        :param hct: Hematocrit (%)
        :param wbc_10e3_ul: White blood cell count (x10^3/uL)
        :param gcs: GCS total
        :param age: Age (years)
        :param chronic_organ_failure: Severe chronic organ failure or immunocompromised
        :param admission_type: Admission category
        :return: {apache2, aps, age_points, chronic_health_points, mortality_estimate, breakdown}
        """
        # --- APS individual item scoring ---
        def score_temp(t):
            if t >= 41 or t < 30: return 4
            if t >= 39 or t < 32: return 3
            if t < 34: return 2
            if t >= 38.5 or t < 36: return 1
            return 0

        def score_map(m):
            if m >= 160 or m <= 49: return 4
            if m >= 130: return 3
            if m >= 110 or m <= 69: return 2
            return 0

        def score_hr(h):
            if h >= 180 or h <= 39: return 4
            if h >= 140 or h <= 54: return 3
            if h >= 110 or h <= 69: return 2
            return 0

        def score_rr(r):
            if r >= 50 or r <= 5: return 4
            if r >= 35: return 3
            if r <= 9: return 2
            if r >= 25 or r <= 11: return 1
            return 0

        def score_oxy(fio2_, pao2_, aado2_):
            if fio2_ >= 0.5:
                if aado2_ is None:
                    return None  # cannot compute
                if aado2_ >= 500: return 4
                if aado2_ >= 350: return 3
                if aado2_ >= 200: return 2
                return 0
            else:
                if pao2_ is None:
                    return None
                if pao2_ < 55: return 4
                if pao2_ < 60: return 3
                if pao2_ < 70: return 1
                return 0

        def score_ph(p):
            # APACHE II original (Knaus 1985) pH score table
            # >=7.70:4, 7.60-7.69:3, 7.50-7.59:1, 7.33-7.49:0,
            # 7.25-7.32:2, 7.15-7.24:3, <7.15:4
            if p >= 7.70 or p < 7.15: return 4
            if p >= 7.60 or p < 7.25: return 3
            if p < 7.33: return 2
            if p >= 7.50: return 1
            return 0

        def score_na(n):
            if n >= 180 or n <= 110: return 4
            if n >= 160 or n <= 119: return 3
            if n >= 155 or n <= 129: return 2
            if n >= 150: return 1
            return 0

        def score_k(kk):
            if kk >= 7 or kk < 2.5: return 4
            if kk >= 6: return 3
            if 2.5 <= kk < 3.0: return 2
            if kk >= 5.5 or kk < 3.5: return 1
            return 0

        def score_cr(c, arf):
            base = 0
            if c >= 3.5: base = 4
            elif c >= 2: base = 3
            elif c >= 1.5: base = 2
            elif c < 0.6: base = 2
            else: base = 0
            return base * 2 if arf else base

        def score_hct(h):
            if h >= 60 or h < 20: return 4
            if h >= 50 or h < 30: return 2
            if h >= 46: return 1
            return 0

        def score_wbc(w):
            if w >= 40 or w < 1: return 4
            if w >= 20 or w < 3: return 2
            if w >= 15: return 1
            return 0

        def score_age(a):
            if a >= 75: return 6
            if a >= 65: return 5
            if a >= 55: return 3
            if a >= 45: return 2
            return 0

        def score_chronic(ch, atype):
            if not ch:
                return 0
            return 5 if atype == "non_op" or atype == "emergency_post_op" else 2

        oxy = score_oxy(fio2, pao2, a_ado2)
        if oxy is None:
            return {
                "error": (
                    "Cannot compute oxygenation score: provide a_ado2 when FiO2 >= 0.5, "
                    "or pao2 when FiO2 < 0.5."
                )
            }

        breakdown = {
            "temp": score_temp(temp_c),
            "map": score_map(map_mmhg),
            "hr": score_hr(hr),
            "rr": score_rr(rr),
            "oxygenation": oxy,
            "ph": score_ph(ph),
            "na": score_na(na),
            "k": score_k(k),
            "cr": score_cr(cr_mg_dl, acute_renal_failure),
            "hct": score_hct(hct),
            "wbc": score_wbc(wbc_10e3_ul),
            "gcs_points": 15 - gcs,
        }
        aps = sum(breakdown.values())
        age_points = score_age(age)
        chronic_points = score_chronic(chronic_organ_failure, admission_type)
        total = aps + age_points + chronic_points

        return {
            "apache2": total,
            "aps": aps,
            "age_points": age_points,
            "chronic_health_points": chronic_points,
            "breakdown": breakdown,
            "note": (
                "Use worst values within 24 hours of ICU admission. "
                "Mortality estimation requires disease-specific coefficients "
                "and is not returned by this function."
            ),
        }

    def calc_sofa(
        self,
        # Respiration (PaO2/FiO2)
        pao2_fio2_ratio: Optional[float] = None,
        mechanical_ventilation: bool = False,
        # Coagulation
        plt_10e4_ul: Optional[float] = None,
        # Hepatic
        bilirubin_mg_dl: Optional[float] = None,
        # Cardiovascular
        map_mmhg: Optional[float] = None,
        vasopressor: Literal[
            "none",
            "dopamine_low",        # <=5 ug/kg/min or dobutamine only
            "dopamine_mid",        # 5.1-15 ug/kg/min or norepinephrine/epinephrine <=0.1 ug/kg/min
            "dopamine_high",       # >15 ug/kg/min or norepinephrine/epinephrine >0.1 ug/kg/min
        ] = "none",
        # Central nervous system
        gcs: Optional[int] = None,
        # Renal
        cr_mg_dl: Optional[float] = None,
        urine_output_ml_per_day: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Calculate SOFA (Sequential Organ Failure Assessment) score.
        Used for sepsis diagnosis (Sepsis-3) and serial ICU assessment.

        :param pao2_fio2_ratio: PaO2/FiO2 ratio (mmHg). Example: PaO2 80, FiO2 0.4 = 200
        :param mechanical_ventilation: Whether on mechanical ventilation (used for P/F<200 scoring)
        :param plt_10e4_ul: Platelets (x10^4/uL, Japanese notation)
        :param bilirubin_mg_dl: Total bilirubin (mg/dL)
        :param map_mmhg: Mean arterial pressure (mmHg)
        :param vasopressor: Vasopressor use status. See details below
        :param gcs: GCS total
        :param cr_mg_dl: Serum Cr (mg/dL)
        :param urine_output_ml_per_day: Daily urine output (mL/day)
        :return: {sofa, breakdown, missing_organs, note}

        Vasopressor categories:
        - none: No vasopressors
        - dopamine_low: Dopamine <=5 ug/kg/min or dobutamine only
        - dopamine_mid: Dopamine 5.1-15 or norepinephrine/epinephrine <=0.1 ug/kg/min
        - dopamine_high: Dopamine >15 or norepinephrine/epinephrine >0.1 ug/kg/min

        Missing items are not included in the score and shown as None in breakdown.
        """
        breakdown: Dict[str, Optional[int]] = {}
        missing = []

        # Respiration
        if pao2_fio2_ratio is not None:
            if pao2_fio2_ratio >= 400:
                pts = 0
            elif pao2_fio2_ratio >= 300:
                pts = 1
            elif pao2_fio2_ratio >= 200:
                pts = 2
            elif pao2_fio2_ratio >= 100:
                pts = 3 if mechanical_ventilation else 2
            else:
                pts = 4 if mechanical_ventilation else 2
            breakdown["respiration"] = pts
        else:
            breakdown["respiration"] = None
            missing.append("respiration (PaO2/FiO2)")

        # Coagulation (PLT is defined in x10^9/L, but Japanese notation x10^4/uL is equivalent*10)
        if plt_10e4_ul is not None:
            plt_10e9_l = plt_10e4_ul * 10  # Convert to x10^9/L
            if plt_10e9_l >= 150: pts = 0
            elif plt_10e9_l >= 100: pts = 1
            elif plt_10e9_l >= 50: pts = 2
            elif plt_10e9_l >= 20: pts = 3
            else: pts = 4
            breakdown["coagulation"] = pts
        else:
            breakdown["coagulation"] = None
            missing.append("coagulation (PLT)")

        # Hepatic
        if bilirubin_mg_dl is not None:
            if bilirubin_mg_dl < 1.2: pts = 0
            elif bilirubin_mg_dl < 2.0: pts = 1
            elif bilirubin_mg_dl < 6.0: pts = 2
            elif bilirubin_mg_dl < 12.0: pts = 3
            else: pts = 4
            breakdown["liver"] = pts
        else:
            breakdown["liver"] = None
            missing.append("liver (bilirubin)")

        # Cardiovascular
        if vasopressor == "dopamine_high":
            pts = 4
        elif vasopressor == "dopamine_mid":
            pts = 3
        elif vasopressor == "dopamine_low":
            pts = 2
        elif map_mmhg is not None:
            pts = 1 if map_mmhg < 70 else 0
        else:
            pts = None
            missing.append("cardiovascular (MAP or vasopressor)")
        breakdown["cardiovascular"] = pts

        # Central nervous system
        if gcs is not None:
            if gcs == 15: pts = 0
            elif gcs >= 13: pts = 1
            elif gcs >= 10: pts = 2
            elif gcs >= 6: pts = 3
            else: pts = 4
            breakdown["cns"] = pts
        else:
            breakdown["cns"] = None
            missing.append("cns (GCS)")

        # Renal
        cr_pts = None
        uo_pts = None
        if cr_mg_dl is not None:
            if cr_mg_dl < 1.2: cr_pts = 0
            elif cr_mg_dl < 2.0: cr_pts = 1
            elif cr_mg_dl < 3.5: cr_pts = 2
            elif cr_mg_dl < 5.0: cr_pts = 3
            else: cr_pts = 4
        if urine_output_ml_per_day is not None:
            if urine_output_ml_per_day < 200: uo_pts = 4
            elif urine_output_ml_per_day < 500: uo_pts = 3

        if cr_pts is not None and uo_pts is not None:
            renal_pts = max(cr_pts, uo_pts)
        elif cr_pts is not None:
            renal_pts = cr_pts
        elif uo_pts is not None:
            renal_pts = uo_pts
        else:
            renal_pts = None
            missing.append("renal (Cr or urine output)")
        breakdown["renal"] = renal_pts

        total = sum(v for v in breakdown.values() if v is not None)

        return {
            "sofa": total,
            "breakdown": breakdown,
            "missing_organs": missing,
            "note": (
                "Sepsis-3 definition: Sepsis is diagnosed when infection causes "
                "an acute SOFA increase (>=2 points). "
                "Serial assessment trends within the same patient are important. "
                "This function does not include missing items in the score (treated as None, not 0). "
                "If not all items are available, supplement missing items and recalculate."
            ),
        }

    # =========================================================================
    # Gastrointestinal
    # =========================================================================

    def calc_glasgow_blatchford(
        self,
        bun_mg_dl: float,
        hb_g_dl: float,
        sex: Literal["M", "F"],
        sbp_mmhg: int,
        hr: int,
        melena: bool,
        syncope: bool,
        hepatic_disease: bool,
        cardiac_failure: bool,
    ) -> Dict[str, Any]:
        """Calculate Glasgow-Blatchford Score (GBS) (risk stratification for upper GI bleeding).

        :param bun_mg_dl: BUN (mg/dL)
        :param hb_g_dl: Hemoglobin (g/dL)
        :param sex: Sex ("M"/"F")
        :param sbp_mmhg: Systolic blood pressure (mmHg)
        :param hr: Heart rate (/min)
        :param melena: Melena present
        :param syncope: Syncope present
        :param hepatic_disease: History of hepatic disease
        :param cardiac_failure: History of cardiac failure
        :return: {gbs, risk_category, note}
        """
        score = 0

        # BUN
        if bun_mg_dl >= 70: score += 6
        elif bun_mg_dl >= 28: score += 4
        elif bun_mg_dl >= 22.4: score += 3
        elif bun_mg_dl >= 18.2: score += 2

        # Hb (sex-specific thresholds)
        if sex == "M":
            if hb_g_dl < 10: score += 6
            elif hb_g_dl < 12: score += 3
            elif hb_g_dl < 13: score += 1
        else:
            if hb_g_dl < 10: score += 6
            elif hb_g_dl < 12: score += 1

        # SBP
        if sbp_mmhg < 90: score += 3
        elif sbp_mmhg < 100: score += 2
        elif sbp_mmhg < 110: score += 1

        # Other
        if hr >= 100: score += 1
        if melena: score += 1
        if syncope: score += 2
        if hepatic_disease: score += 2
        if cardiac_failure: score += 2

        # Risk assessment
        if score == 0:
            cat = "very_low (outpatient management may be considered)"
        elif score <= 3:
            cat = "low"
        elif score <= 7:
            cat = "moderate"
        else:
            cat = "high (consider urgent intervention)"

        return {
            "gbs": score,
            "risk_category": cat,
            "note": "GBS=0 is a candidate for outpatient management. >=7 often requires intervention.",
        }

    def calc_ranson_criteria(
        self,
        timing: Literal["admission", "48h"],
        # Admission items
        age: Optional[int] = None,
        wbc_10e3_ul: Optional[float] = None,
        glucose_mg_dl: Optional[float] = None,
        ldh_u_l: Optional[float] = None,
        ast_u_l: Optional[float] = None,
        # 48-hour items
        hct_drop_pct: Optional[float] = None,
        bun_increase_mg_dl: Optional[float] = None,
        ca_mg_dl: Optional[float] = None,
        pao2_mmhg: Optional[float] = None,
        base_deficit: Optional[float] = None,
        fluid_sequestration_l: Optional[float] = None,
        # Etiology
        gallstone_etiology: bool = False,
    ) -> Dict[str, Any]:
        """Calculate Ranson criteria (severity assessment for acute pancreatitis).
        Evaluates 5 admission items and 6 items at 48 hours separately.

        :param timing: "admission" or "48h" (at 48 hours)
        :param gallstone_etiology: True for gallstone pancreatitis (some thresholds change)
        :return: {timing, score, criteria_met, note}

        Note: In Japan, JSS-CT grade and JMHW severity criteria are more commonly used.
              This function implements the original Western Ranson criteria as-is.
        """
        criteria_met = []

        if timing == "admission":
            # Thresholds differ for gallstone vs non-gallstone etiology
            if gallstone_etiology:
                age_th, wbc_th, glu_th, ldh_th, ast_th = 70, 18, 220, 400, 250
            else:
                age_th, wbc_th, glu_th, ldh_th, ast_th = 55, 16, 200, 350, 250

            if age is not None and age > age_th:
                criteria_met.append(f"age>{age_th}")
            if wbc_10e3_ul is not None and wbc_10e3_ul > wbc_th:
                criteria_met.append(f"WBC>{wbc_th}")
            if glucose_mg_dl is not None and glucose_mg_dl > glu_th:
                criteria_met.append(f"glucose>{glu_th}")
            if ldh_u_l is not None and ldh_u_l > ldh_th:
                criteria_met.append(f"LDH>{ldh_th}")
            if ast_u_l is not None and ast_u_l > ast_th:
                criteria_met.append(f"AST>{ast_th}")

        elif timing == "48h":
            if hct_drop_pct is not None and hct_drop_pct > 10:
                criteria_met.append("Hct drop>10%")
            if bun_increase_mg_dl is not None and bun_increase_mg_dl > 5:
                criteria_met.append("BUN increase>5")
            if ca_mg_dl is not None and ca_mg_dl < 8:
                criteria_met.append("Ca<8")
            if pao2_mmhg is not None and pao2_mmhg < 60:
                criteria_met.append("PaO2<60")
            if base_deficit is not None and base_deficit > 4:
                criteria_met.append("base deficit>4")
            if fluid_sequestration_l is not None and fluid_sequestration_l > 6:
                criteria_met.append("fluid sequestration>6L")

        return {
            "timing": timing,
            "score": len(criteria_met),
            "criteria_met": criteria_met,
            "note": (
                "A combined admission + 48h total >=3 suggests severe pancreatitis. "
                "In Japan, concurrent use of JSS-CT grade / JMHW severity criteria is recommended."
            ),
        }

    # =========================================================================
    # Hematology / Coagulation
    # =========================================================================

    def calc_dic_score(
        self,
        criteria: Literal["isth_overt", "jmhw_hematologic", "jmhw_non_hematologic"],
        plt_10e4_ul: float,
        fdp_ug_ml: Optional[float] = None,
        d_dimer_ug_ml: Optional[float] = None,
        fibrinogen_mg_dl: Optional[float] = None,
        pt_ratio: Optional[float] = None,
        pt_seconds_prolongation: Optional[float] = None,
        underlying_disease: bool = True,
        bleeding_symptom: bool = False,
        organ_failure: bool = False,
    ) -> Dict[str, Any]:
        """Calculate DIC diagnostic score (ISTH overt / JMHW 2017 revised Hematologic / Non-hematologic type).

        :param criteria: "isth_overt" / "jmhw_hematologic" / "jmhw_non_hematologic"
        :param plt_10e4_ul: Platelets (x10^4/uL, Japanese notation)
        :param fdp_ug_ml: FDP (ug/mL)
        :param d_dimer_ug_ml: D-dimer (ug/mL). Can substitute for FDP in ISTH.
        :param fibrinogen_mg_dl: Fibrinogen (mg/dL)
        :param pt_ratio: PT ratio (used in Japanese criteria)
        :param pt_seconds_prolongation: PT prolongation in seconds (used in ISTH)
        :param underlying_disease: Presence of underlying disease for DIC
        :param bleeding_symptom: Bleeding symptoms present (Japanese criteria only)
        :param organ_failure: Organ failure present (Japanese criteria only)
        :return: {criteria, score, threshold_for_dic, dic_diagnosis, breakdown}

        Note: JMHW criteria implements the 2017 revised version. Hematologic type excludes platelet scoring.
        """
        score = 0
        breakdown = {}

        if criteria == "isth_overt":
            # Underlying disease is required
            if not underlying_disease:
                return {"error": "ISTH overt DIC requires the presence of an underlying disease."}

            # PLT
            if plt_10e4_ul < 5: pts = 2
            elif plt_10e4_ul < 10: pts = 1
            else: pts = 0
            score += pts; breakdown["plt"] = pts

            # FDP or D-dimer (fibrin-related marker)
            marker = fdp_ug_ml if fdp_ug_ml is not None else d_dimer_ug_ml
            if marker is None:
                return {"error": "Either FDP or D-dimer is required."}
            # ISTH original is defined by FDP (thresholds like >=10 for 2 pts, >=5 for 1 pt are lab-dependent)
            # Here simplified as moderate increase=2, strong increase=3
            # Note: Recalibration to institutional reference ranges is recommended
            if marker >= 25: pts = 3  # strong increase
            elif marker >= 5: pts = 2  # moderate increase
            elif marker > 1: pts = 0  # no increase
            else: pts = 0
            score += pts; breakdown["fibrin_marker"] = pts

            # PT prolongation (seconds)
            if pt_seconds_prolongation is not None:
                if pt_seconds_prolongation >= 6: pts = 2
                elif pt_seconds_prolongation >= 3: pts = 1
                else: pts = 0
                score += pts; breakdown["pt_prolongation"] = pts

            # Fibrinogen
            if fibrinogen_mg_dl is not None:
                pts = 1 if fibrinogen_mg_dl < 100 else 0
                score += pts; breakdown["fibrinogen"] = pts

            return {
                "criteria": "ISTH overt DIC (2001)",
                "score": score,
                "threshold_for_dic": 5,
                "dic_diagnosis": score >= 5,
                "breakdown": breakdown,
                "note": ">=5 for overt DIC. <5 suggests non-overt DIC; serial reassessment required.",
            }

        elif criteria in ("jmhw_hematologic", "jmhw_non_hematologic"):
            is_hematologic = criteria == "jmhw_hematologic"

            # Underlying disease
            if underlying_disease:
                score += 1; breakdown["underlying_disease"] = 1

            # Clinical symptoms
            if bleeding_symptom and not is_hematologic:
                # Hematologic type does not score bleeding symptoms (due to thrombocytopenia)
                score += 1; breakdown["bleeding"] = 1
            if organ_failure:
                score += 1; breakdown["organ_failure"] = 1

            # Platelets (not scored in hematologic type)
            if not is_hematologic:
                if plt_10e4_ul < 5: pts = 3
                elif plt_10e4_ul < 8: pts = 2
                elif plt_10e4_ul < 12: pts = 1
                else: pts = 0
                score += pts; breakdown["plt"] = pts

            # FDP
            if fdp_ug_ml is not None:
                if fdp_ug_ml >= 40: pts = 3
                elif fdp_ug_ml >= 20: pts = 2
                elif fdp_ug_ml >= 10: pts = 1
                else: pts = 0
                score += pts; breakdown["fdp"] = pts

            # Fibrinogen
            if fibrinogen_mg_dl is not None:
                if fibrinogen_mg_dl < 100: pts = 2
                elif fibrinogen_mg_dl < 150: pts = 1
                else: pts = 0
                score += pts; breakdown["fibrinogen"] = pts

            # PT ratio
            if pt_ratio is not None:
                if pt_ratio >= 1.67: pts = 2
                elif pt_ratio >= 1.25: pts = 1
                else: pts = 0
                score += pts; breakdown["pt_ratio"] = pts

            threshold = 4 if is_hematologic else 7
            return {
                "criteria": (
                    "JMHW Hematologic Type (2017)" if is_hematologic
                    else "JMHW Non-Hematologic Type (2017)"
                ),
                "score": score,
                "threshold_for_dic": threshold,
                "dic_diagnosis": score >= threshold,
                "breakdown": breakdown,
                "note": (
                    "Hematologic type >=4, Non-hematologic type >=7 for DIC. "
                    "Select hematologic type for hematologic malignancies such as leukemia."
                ),
            }

    # =========================================================================
    # Acid-base
    # =========================================================================

    def calc_acid_base_analysis(
        self,
        ph: float,
        pco2: float,
        hco3: float,
        na: Optional[float] = None,
        cl: Optional[float] = None,
        albumin_g_dl: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Integrated arterial blood gas analysis: primary disorder identification +
        compensation prediction + AG calculation.

        :param ph: Arterial blood pH
        :param pco2: PaCO2 (mmHg)
        :param hco3: HCO3- (mEq/L)
        :param na: Serum Na (mEq/L). Required for AG calculation.
        :param cl: Serum Cl (mEq/L). Required for AG calculation.
        :param albumin_g_dl: Albumin (g/dL). Used for corrected AG.
        :return: {primary_disorder, expected_compensation, compensation_status,
                  anion_gap, corrected_anion_gap, mixed_disorder_suspected, summary}
        """
        result: Dict[str, Any] = {}

        # Primary disorder identification
        if ph < 7.35:
            if hco3 < 22:
                primary = "metabolic_acidosis"
            elif pco2 > 45:
                primary = "respiratory_acidosis"
            else:
                primary = "indeterminate_acidemia"
        elif ph > 7.45:
            if hco3 > 26:
                primary = "metabolic_alkalosis"
            elif pco2 < 35:
                primary = "respiratory_alkalosis"
            else:
                primary = "indeterminate_alkalemia"
        else:
            primary = "normal_or_mixed"

        result["primary_disorder"] = primary

        # Compensation prediction
        expected = None
        comp_status = None
        if primary == "metabolic_acidosis":
            # Winters: Expected PaCO2 = 1.5 x HCO3 + 8 +/- 2
            expected = 1.5 * hco3 + 8
            result["expected_compensation"] = (
                f"PaCO2 = {expected-2:.1f}-{expected+2:.1f} mmHg (Winters formula)"
            )
            if pco2 < expected - 2:
                comp_status = "respiratory_alkalosis_concomitant (decrease beyond expected compensation)"
            elif pco2 > expected + 2:
                comp_status = "respiratory_acidosis_concomitant (inadequate compensation)"
            else:
                comp_status = "appropriate_compensation"
        elif primary == "metabolic_alkalosis":
            # Expected PaCO2 = HCO3 + 15 (approximation)
            expected = hco3 + 15
            result["expected_compensation"] = (
                f"PaCO2 approx {expected:.1f} mmHg (simplified formula)"
            )
            if pco2 < expected - 5:
                comp_status = "respiratory_alkalosis_concomitant"
            elif pco2 > expected + 5:
                comp_status = "respiratory_acidosis_concomitant"
            else:
                comp_status = "appropriate_compensation"
        elif primary == "respiratory_acidosis":
            # Acute: delta-HCO3 approx delta-PaCO2 x 0.1, Chronic: x 0.35
            delta_pco2 = pco2 - 40
            expected_acute = 24 + delta_pco2 * 0.1
            expected_chronic = 24 + delta_pco2 * 0.35
            result["expected_compensation"] = (
                f"Acute: HCO3 approx {expected_acute:.1f}, Chronic: HCO3 approx {expected_chronic:.1f}"
            )
        elif primary == "respiratory_alkalosis":
            delta_pco2 = 40 - pco2
            expected_acute = 24 - delta_pco2 * 0.2
            expected_chronic = 24 - delta_pco2 * 0.5
            result["expected_compensation"] = (
                f"Acute: HCO3 approx {expected_acute:.1f}, Chronic: HCO3 approx {expected_chronic:.1f}"
            )

        if comp_status:
            result["compensation_status"] = comp_status

        # AG calculation
        if na is not None and cl is not None:
            ag = na - cl - hco3
            result["anion_gap"] = round(ag, 1)
            if albumin_g_dl is not None:
                # Corrected AG: AG + 2.5 x (4 - albumin)
                corrected_ag = ag + 2.5 * (4.0 - albumin_g_dl)
                result["corrected_anion_gap"] = round(corrected_ag, 1)
                result["ag_interpretation"] = (
                    "high_anion_gap" if corrected_ag > 12
                    else "normal_anion_gap"
                )
            else:
                result["ag_interpretation"] = (
                    "high_anion_gap" if ag > 12 else "normal_anion_gap"
                )

        # Brief summary
        result["summary"] = f"primary: {primary}"
        if comp_status and comp_status != "appropriate_compensation":
            result["mixed_disorder_suspected"] = True

        return result

    # =========================================================================
    # Renal function (additional)
    # =========================================================================

    def calc_egfr_jsn(
        self,
        cr: float,
        age: int,
        sex: Literal["M", "F"],
    ) -> Dict[str, Any]:
        """Calculate eGFR using the Japanese GFR estimation equation
        (Japanese Society of Nephrology [JSN] 2009).
        This equation is widely used in Japan.

        :param cr: Serum creatinine (enzymatic method, mg/dL)
        :param age: Age (years)
        :param sex: "M" or "F"
        :return: {egfr, formula, ckd_stage, note}

        Formula: eGFR = 194 x Cr^(-1.094) x age^(-0.287) x (0.739 for female)
        """
        egfr = 194 * (cr ** -1.094) * (age ** -0.287)
        if sex == "F":
            egfr *= 0.739

        if egfr >= 90:
            stage = "G1"
        elif egfr >= 60:
            stage = "G2"
        elif egfr >= 45:
            stage = "G3a"
        elif egfr >= 30:
            stage = "G3b"
        elif egfr >= 15:
            stage = "G4"
        else:
            stage = "G5"

        return {
            "egfr": round(egfr, 1),
            "unit": "mL/min/1.73m2",
            "formula": "JSN 2009 (Japanese GFR estimation equation)",
            "ckd_stage": stage,
            "note": (
                "Use Cr measured by enzymatic method. Jaffe method Cr reads low and is not suitable. "
                "For drug dosage adjustment, use CCr (absolute value) from Cockcroft-Gault, not this value."
            ),
        }

    def calc_free_water_deficit(
        self,
        na_measured: float,
        weight_kg: float,
        sex: Literal["M", "F"],
        age: int,
        na_target: float = 140,
    ) -> Dict[str, Any]:
        """Calculate free water deficit in hypernatremia.

        :param na_measured: Measured Na (mEq/L)
        :param weight_kg: Body weight (kg)
        :param sex: "M" or "F"
        :param age: Age (years). TBW ratio is reduced for age >=65.
        :param na_target: Target Na (mEq/L), default 140
        :return: {free_water_deficit_L, tbw_L, note}

        Formula: Free water deficit = TBW x (measured Na / target Na - 1)
        TBW ratio: Male 0.6, Female 0.5 (elderly: 0.5 and 0.45 respectively)
        """
        if na_measured <= na_target:
            return {
                "error": (
                    f"Measured Na ({na_measured}) is at or below target Na ({na_target}), "
                    f"so free water deficit does not exist."
                )
            }

        if age >= 65:
            tbw_ratio = 0.50 if sex == "M" else 0.45
        else:
            tbw_ratio = 0.60 if sex == "M" else 0.50

        tbw = weight_kg * tbw_ratio
        deficit = tbw * (na_measured / na_target - 1)
        suggested_24h = deficit / 2  # Half-correction suggestion assuming chronic case

        return {
            "free_water_deficit_L": round(deficit, 2),
            "tbw_L": round(tbw, 2),
            "tbw_ratio_used": tbw_ratio,
            "suggested_24h_volume_L": round(suggested_24h, 2),
            "max_correction_rate": "<=10 mEq/L/24h (chronic) or <=1 mEq/L/h (acute)",
            "note": (
                "This value represents free water deficit only. Maintenance fluid volume and "
                "oral/enteral intake should be considered separately. "
                "Rapid Na correction can cause cerebral edema/demyelination; for chronic cases, "
                "aim for half-correction over 24 hours. "
                "Note the free water content of IV fluids (5% dextrose=100%, half-normal saline=50%, normal saline=0%)."
            ),
        }

    # =========================================================================
    # Comment stubs (candidates for implementation in Phase 1.5+)
    # =========================================================================
    # The following will be implemented in order of frequency based on Phase 1 logs.
    #
    # def calc_grace_score(...): ACS admission risk (acute coronary syndrome)
    # def calc_timi_score(type, ...): NSTEMI/STEMI combined
    # def calc_pesi(simplified=False, ...): PE severity
    # def calc_bisap(...): Acute pancreatitis simplified version
    # def calc_calvert_carboplatin(target_auc, gfr): Calvert formula (GFR cap 125)
    # def calc_meld_3(...): MELD 3.0 (UNOS 2023~)
    # def calc_na_correction_rate(...): Na correction rate upper limit warning
    #
    # === TDM (separate SKILL) ===
    # Vancomycin TDM, aminoglycoside TDM, etc. are not part of this tool collection
    # but will be implemented as independent SKILLs (vancomycin-tdm, etc.) using
    # Pyodide workflows.
    # Reason: The calculation -> visualization -> what-if sequence works better as
    # an interactive workflow on Pyodide than as single tool invocations.
    # This also makes it easier to delineate roles with each institution's
    # pharmacy TDM support services.
