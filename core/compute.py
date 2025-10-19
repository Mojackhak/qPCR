#%%
import os
import re
import pandas as pd
from typing import Tuple, Optional

def compute_ddct(
    excel_path: str,
    control_group_regex: str,
    ref_gene_regex: str,
    output_path: Optional[str] = None,
    # --- Column mapping (defaults match your spec) ---
    control_search_col: str = "Target",   # where to detect control group (e.g., matches "CTR")
    ref_search_col: str = "Sample",       # where to detect reference gene (e.g., matches "B-ACTIN")
    sample_name_col: str = "Target",      # holds sample labels like "CTR-1", "MT-OGD-7"
    cq_col: str = "Cq",
    well_col: str = "Well",
    sheet_name=0,
    # --- Behavior toggles ---
    exclude_ref_in_sample_sheet: bool = False,  # sample sheet means over target genes only
    assume_case_insensitive_regex: bool = True, # compile regexes with IGNORECASE
    # --- Outlier filtering options ---
    outlier_method: str = "mad",          # one of {"mad","iqr","zscore"}
    outlier_threshold: float = 3.0,        # MAD/z-score: # of robust SDs; IQR: multiplier (1.5–3 typical)
    outlier_min_reps: int = 3,             # require >= this many wells in a (Sample × Gene) group to filter
    record_outliers: bool = True,           # write removed wells to an "outliers" sheet if any
    enable_outlier_filter: bool = True  # master switch to enable/disable outlier filtering
) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Compute ΔCt, ΔΔCt and Fold Change (2^−ΔΔCt) from a qPCR Excel file.

    Parameters
    ----------
    excel_path : str
        Path to input Excel.
    control_group_regex : str
        Regex that identifies the *control condition* rows (searched in `control_search_col`).
        Example: r"^CTR" matches CTR samples like "CTR-1", "CTR-2".
    ref_gene_regex : str
        Regex that identifies the *reference gene* (searched in `ref_search_col`).
        Example: r"ACTB|B[-_ ]?ACTIN".
    output_path : Optional[str]
        Path for the output Excel. If None, writes next to input as "<stem>_ddct.xlsx".
    control_search_col : str
        Column where control group regex is applied (default "Target", per your spec).
    ref_search_col : str
        Column where reference gene regex is applied (default "Sample", per your spec).
    sample_name_col : str
        Column that stores sample labels like "CTR-1", "MT-OGD-7" (default "Target").
    cq_col : str
        Ct/Cq values column (default "Cq").
    well_col : str
        Well identifier column (default "Well").
    sheet_name : any
        Sheet index or name to read (default 0).
    exclude_ref_in_sample_sheet : bool
        If True, sample-sheet means exclude reference gene rows.
    assume_case_insensitive_regex : bool
        If True, regexes compiled with re.IGNORECASE.
    outlier_method : str
        Method for outlier detection on Cq within each (Sample × gene) group.
        One of {"mad", "iqr", "zscore"}. Default "mad".
    outlier_threshold : float
        Threshold for outlier detection:
        - For "mad" and "zscore": number of robust standard deviations (e.g., 3.0).
        - For "iqr": multiplier of IQR (typical 1.5 to 3).
    outlier_min_reps : int
        Minimum number of wells in a (Sample × gene) group to apply outlier filtering.
    record_outliers : bool
        If True, removed outlier wells are saved to an "outliers" sheet in the output Excel.
    enable_outlier_filter : bool
        If False, disables outlier filtering regardless of `outlier_method`.

    Returns
    -------
    well_df : pd.DataFrame
        Per-well results with columns:
        ["Group","Sample","Gene","Well","Cq","ΔCt","ΔΔCt","Fold Change"].
    sample_df : pd.DataFrame
        Per-sample means with columns:
        ["Group","Sample","Gene","Cq","ΔCt","ΔΔCt","Fold Change"].
    output_path : str
        Output Excel file path, containing sheets "well" and "sample" (and "outliers" if enabled).

    Notes
    -----
    - ΔCt(well) = Cq(well) − mean_{reference gene, same Sample}(Cq).
    - ΔΔCt(well) = ΔCt(well) − ⟨ mean_ΔCt ⟩_controls, same gene.
      Baseline is computed in two steps: (i) within controls, take the mean ΔCt per Sample × gene; (ii) average these per-sample means across all control Samples to get one baseline per gene (column given by `ref_search_col`).
    - Fold Change = 2^(−ΔΔCt).
    - Samples are parsed as: Group = sample_label.rsplit('-', 1)[0]; Sample = sample_label (full).
    - Rows with missing/non-numeric Cq are dropped.
    - If a sample lacks reference-gene measurements, ΔCt cannot be computed for that sample.
    - If a gene lacks control-group rows, ΔΔCt cannot be computed for that gene.
    - Outlier filtering is applied to Cq within each (Sample × gene) group before computing reference means; groups with < outlier_min_reps are left unfiltered.
    """

    def _flag_outliers(s: pd.Series, method: str, thresh: float) -> pd.Series:
        s = s.astype(float)
        if method == "mad":
            med = s.median()
            mad = 1.4826 * (s - med).abs().median()
            if mad == 0 or pd.isna(mad):
                return pd.Series(False, index=s.index)
            score = (s - med).abs() / mad
            return score > thresh
        elif method == "iqr":
            q1 = s.quantile(0.25)
            q3 = s.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0 or pd.isna(iqr):
                return pd.Series(False, index=s.index)
            lo = q1 - thresh * iqr
            hi = q3 + thresh * iqr
            return (s < lo) | (s > hi)
        elif method == "zscore":
            mu = s.mean()
            sd = s.std(ddof=0)
            if sd == 0 or pd.isna(sd):
                return pd.Series(False, index=s.index)
            z = (s - mu).abs() / sd
            return z > thresh
        else:
            return pd.Series(False, index=s.index)

    # Load
    df = pd.read_excel(excel_path, sheet_name=sheet_name)

    # Basic column checks
    required_cols = {control_search_col, ref_search_col, sample_name_col, cq_col, well_col}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required column(s): {sorted(missing)}. "
            f"Present columns: {sorted(df.columns)}"
        )

    # 0) Strip out rows where Cq is missing or non-numeric
    #    Coerce to numeric; drop NaN
    df = df.copy()
    df[cq_col] = pd.to_numeric(df[cq_col], errors="coerce")
    df = df.dropna(subset=[cq_col])

    # Normalized text columns for robust matching
    for col in [control_search_col, ref_search_col, sample_name_col]:
        df[col] = df[col].astype(str)

    # Compile regexes
    flags = re.IGNORECASE if assume_case_insensitive_regex else 0
    control_re = re.compile(control_group_regex, flags)
    ref_re = re.compile(ref_gene_regex, flags)

    # Mark reference-gene rows and control-group rows
    ref_mask = df[ref_search_col].apply(lambda x: bool(ref_re.search(x)))
    control_mask = df[control_search_col].apply(lambda x: bool(control_re.search(x)))

    # Sanity check: ensure control regex matched at least one row
    if not control_mask.any():
        raise ValueError(
            "No control rows matched. Check `control_group_regex` and `control_search_col`. "
            "If your layout is conventional (Sample = biosample like 'CTR-1', Target = gene), "
            "use control_search_col='Sample', ref_search_col='Target', sample_name_col='Sample'."
        )

    # Parse "Group" and "_SampleLabel" from sample_name_col (rsplit by last '-')
    def _split_group_sample(label: str):
        if "-" in label:
            head, _ = label.rsplit("-", 1)
            return head, label
        else:
            # If no '-', treat entire string as the group and sample
            return label, label

    parsed = df[sample_name_col].apply(_split_group_sample)
    df["Group"] = parsed.apply(lambda t: t[0])
    df["_SampleLabel"] = parsed.apply(lambda t: t[1])  # full label like "CTR-1"

    # Optional: filter outlier wells by Cq within each (Sample × gene) group
    if enable_outlier_filter:
        # Only evaluate groups with enough replicates
        def _group_flag(g: pd.DataFrame) -> pd.Series:
            if len(g) < outlier_min_reps:
                return pd.Series(False, index=g.index)
            return _flag_outliers(g[cq_col], outlier_method.lower(), outlier_threshold)

        grp_keys = ["_SampleLabel", ref_search_col]
        outlier_mask = df.groupby(grp_keys, dropna=False, group_keys=False).apply(_group_flag, include_groups=False)
        df["_Outlier"] = outlier_mask.reindex(df.index).fillna(False).astype(bool)

        # Optionally store removed wells for auditing
        outliers_df = df.loc[df["_Outlier"], ["Group", "_SampleLabel", ref_search_col, well_col, cq_col]].copy()

        # Drop outliers before ΔCt computation
        df = df.loc[~df["_Outlier"]].copy()

    # 1) ΔCt: subtract mean Cq of reference gene for the SAME Sample (_SampleLabel)
    #     Build map: _SampleLabel -> mean(Cq) for reference rows
    ref_per_sample = (
        df.loc[ref_mask, ["_SampleLabel", cq_col]]
          .groupby("_SampleLabel", dropna=False)[cq_col]
          .mean()
    )

    # Attach ref mean to all rows by _SampleLabel
    df = df.merge(ref_per_sample.rename("ref_mean_cq"), left_on="_SampleLabel", right_index=True, how="left")

    # Rows without reference-gene mean cannot compute ΔCt
    if df["ref_mean_cq"].isna().any():
        missing_samples = sorted(df.loc[df["ref_mean_cq"].isna(), "_SampleLabel"].unique())
        raise ValueError(
            "Reference-gene Cq mean not found for some samples. "
            f"Ensure each Sample has at least one reference-gene well.\n"
            f"Affected Samples: {missing_samples}"
        )

    df["ΔCt"] = df[cq_col] - df["ref_mean_cq"]

    # 2) ΔΔCt baseline: mean ΔCt of CONTROL group for the SAME gene (value in ref_search_col)
    #    First, compute per-control-sample mean ΔCt for each gene, then average across control samples.
    # Compute per-control-sample mean ΔCt within controls for each gene (ref_search_col)
    control_per_sample = (
        df.loc[control_mask, ["_SampleLabel", ref_search_col, "ΔCt"]]
          .groupby(["_SampleLabel", ref_search_col], dropna=False)["ΔCt"]
          .mean()
          .reset_index()
    )

    # Then average across control samples for each gene -> global control baseline per gene
    control_baseline = (
        control_per_sample
          .groupby(ref_search_col, dropna=False)["ΔCt"]
          .mean()
          .rename("control_mean_ΔCt")
    )

    # Merge per-gene control mean ΔCt
    df = df.merge(control_baseline, left_on=ref_search_col, right_index=True, how="left")

    if df["control_mean_ΔCt"].isna().any():
        # Some genes lack control data -> cannot compute ΔΔCt for those genes
        missing_genes = sorted(df.loc[df["control_mean_ΔCt"].isna(), ref_search_col].unique())
        raise ValueError(
            "No control-group rows found for some gene(s). "
            "Add control wells or adjust `control_group_regex` / `control_search_col`.\n"
            f"Affected gene(s) in {ref_search_col}: {missing_genes}"
        )

    # 3) ΔΔCt and Fold Change
    df["ΔΔCt"] = df["ΔCt"] - df["control_mean_ΔCt"]
    df["Fold Change"] = 2.0 ** (-df["ΔΔCt"])

    # 4a) Well sheet
    well_cols = ["Group", "_SampleLabel", ref_search_col, well_col, cq_col, "ΔCt", "ΔΔCt", "Fold Change"]
    well_df = (
        df[well_cols]
          .rename(columns={"_SampleLabel": "Sample", ref_search_col: "Gene"})
          .copy()
          .sort_values(["Gene", "Group", "Sample"], kind="mergesort")
          .reset_index(drop=True)
    )
    # Reorder columns to put Gene first
    col_order = ["Gene", "Group", "Sample", well_col, cq_col, "ΔCt", "ΔΔCt", "Fold Change"]
    well_df = well_df[col_order]

    # 4b) Sample sheet (mean per Sample)
    sample_source = df[~ref_mask].copy() if exclude_ref_in_sample_sheet else df.copy()
    if sample_source.empty:
        raise ValueError(
            "No target-gene rows available for sample-sheet means. "
            "Either your file only contains the reference gene, or the regex filtered everything."
        )

    sample_df = (
        sample_source.groupby(["Group", "_SampleLabel", ref_search_col], dropna=False)[[cq_col, "ΔCt", "ΔΔCt", "Fold Change"]]
            .mean()
            .reset_index()
            .rename(columns={"_SampleLabel": "Sample", ref_search_col: "Gene", cq_col: "Cq"})
            .sort_values(["Gene", "Group", "Sample"], kind="mergesort")
            .reset_index(drop=True)
    )
    # Reorder columns to put Gene first
    col_order = ["Gene", "Group", "Sample", "Cq", "ΔCt", "ΔΔCt", "Fold Change"]
    sample_df = sample_df[col_order]

    # 5) Export
    if output_path is None:
        base, stem = os.path.split(excel_path)
        root, _ = os.path.splitext(stem)
        output_path = os.path.join(base or ".", f"{root}_ddct.xlsx")

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        well_df.to_excel(writer, index=False, sheet_name="well")
        sample_df.to_excel(writer, index=False, sheet_name="sample")
        if record_outliers and "outliers_df" in locals() and not outliers_df.empty:
            (outliers_df
                .rename(columns={"_SampleLabel": "Sample", ref_search_col: "Gene", cq_col: "Cq"})
                .sort_values(["Gene", "Group", "Sample", "Well"], kind="mergesort")
                .to_excel(writer, index=False, sheet_name="outliers")
            )

    return well_df, sample_df, output_path

# --- Example usage (adjust paths/regexes) ---
# well, sample, out = compute_ddct(
#     excel_path=r'/Users/mojackhu/Desktop/pytest/test.xlsx',
#     control_group_regex=r"CTR",
#     ref_gene_regex=r"B[-_ ]?ACTIN|ACTB"
# )
# print(f"Wrote results to: {out}")
# display(well.head()); display(sample.head())
