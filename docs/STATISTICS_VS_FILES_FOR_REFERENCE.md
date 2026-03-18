# Statistics vs Files for Reference: Gap Analysis

This document compares `aiecs/tools/statistics` with `aiecs/tools/files_for_reference` to support the refactor from apisource to stats-only MCP. It provides file correspondence, missing features, and migration candidates.

---

## 1. File Correspondence

### 1.1 Direct Mapping (statistics ↔ files_for_reference)

| statistics | files_for_reference | Relationship |
|------------|---------------------|--------------|
| `data_loader_tool.py` | `data_loader.py` | **Partial overlap** – Both load SPSS/Parquet/CSV. statistics uses BaseTool + pandas_tool; files_for_reference has standalone `load_file()` with SPSS value labels, custom_headers, metadata. |
| `data_profiler_tool.py` | `descriptive_stats.py` | **Partial overlap** – Both do profiling/descriptive stats. statistics delegates to stats_tool; files_for_reference has `describe_all()` with group_by, percentiles, numeric/categorical split, tabulate output. |
| `data_transformer_tool.py` | `data_cleaner.py` | **Partial overlap** – Both handle cleaning/transformation. statistics has transform ops; files_for_reference has `auto_clean()` with strategy (minimal/standard/aggressive), outlier methods (IQR/Z-score/IsolationForest), custom_rules. |
| `statistical_analyzer_tool.py` | `advanced_stats.py` | **Partial overlap** – Both do hypothesis tests, regression, etc. statistics delegates to stats_tool; files_for_reference has `run_analysis()` with 12+ analysis types (correlation, OLS, logistic, ANOVA, ANCOVA, t-test, nonparametric, chi-square, PCA, K-Means, factor analysis, multiple comparison). |
| `data_visualizer_tool.py` | — | **No direct counterpart** – statistics has visualization; files_for_reference uses chart output via table_formatter. |
| `model_trainer_tool.py` | — | **No direct counterpart** – statistics has ML training; files_for_reference focuses on classical stats. |
| — | `table_formatter.py` | **Missing in statistics** – dataframe_to_table, frequency_table, crosstab_table, format_result_for_llm. statistics tools return raw dicts; no tabulate formatting. |
| — | `formula_dsl.py` | **Missing in statistics** – validate_formula, auto_enhance_formula, suggest_formula, FORMULA_REFERENCE_CARD for Wilkinson notation. |
| — | `pipeline.py` | **Missing in statistics** – run_pipeline for multi-step analysis (tool_call, code, formula, transform, condition). |
| — | `sandbox.py` | **Missing in statistics** – execute_code for safe Python execution. |
| — | `server.py` | **Reference only** – MCP server entry; not a module to migrate. |

### 1.2 Files Without Direct Correspondence

| Location | File | Notes |
|----------|------|-------|
| statistics | `__init__.py` | Module init; no correspondence. |
| files_for_reference | `README.md` | Documentation; reference for tool API. |
| files_for_reference | `pyproject.toml` | Package config; reference only. |

---

## 2. Missing Features in Statistics

Features present in `files_for_reference` but missing or weaker in `statistics`:

### 2.1 Data Loading

| Feature | files_for_reference | statistics |
|---------|---------------------|------------|
| SPSS value labels | `apply_labels` in load_file | data_loader_tool uses pyreadstat but does not expose apply_labels or variable/value labels |
| Custom headers at load | `custom_headers` in load_file | Not exposed in data_loader_tool |
| Metadata (variable_labels, value_labels) | Returns `meta` dict | data_loader_tool returns minimal metadata |
| .por (SPSS portable) | Supported | Not explicitly listed |

### 2.2 Descriptive Statistics

| Feature | files_for_reference | statistics |
|---------|---------------------|------------|
| Group-by statistics | `group_by` in describe_all | data_profiler delegates to stats_tool; group_by not clearly exposed |
| Percentiles config | `percentiles` list | stats_tool has percentiles; integration unclear |
| Numeric vs categorical split | Automatic | data_profiler has similar logic |
| Tabulate output (grid/pipe/html/latex) | Built-in | statistics returns raw dicts; no tabulate formatting |

### 2.3 Data Cleaning

| Feature | files_for_reference | statistics |
|---------|---------------------|------------|
| Strategy levels | minimal / standard / aggressive | data_transformer has similar ops but different API |
| Outlier methods | IQR, Z-score, IsolationForest | data_transformer has remove_outliers |
| Custom rules | `custom_rules` (drop_if, cap, fill_mode) | Not in data_transformer |
| Low-variance column filter | Yes | Not explicit |
| Cleaning report | `cleaning_report_text` | Not in data_transformer |

### 2.4 Advanced Statistics

| Feature | files_for_reference | statistics |
|---------|---------------------|------------|
| ANCOVA | Yes | stats_tool may not expose |
| Two-way ANOVA | Yes (factor as list) | stats_tool has anova |
| Factor analysis (EFA) | Yes | Not in stats_tool |
| Multiple comparison correction | Bonferroni, FDR BH | stats_tool has post_hoc Tukey |
| Point-biserial correlation | Yes | Not explicit |
| Wilkinson formula support | Via formula_dsl | Not in statistics |

### 2.5 Table Formatting

| Feature | files_for_reference | statistics |
|---------|---------------------|------------|
| Tabulate formats | grid, pipe, html, latex, csv, etc. | None |
| Frequency table | frequency_table() | Via stats_tool describe |
| Crosstab | crosstab_table() with normalize | Not in statistics |
| format_result_for_llm | Yes | No |

### 2.6 Formula DSL

| Feature | files_for_reference | statistics |
|---------|---------------------|------------|
| Formula validation | validate_formula() | None |
| Auto-enhance formula | auto_enhance_formula() | None |
| Formula suggestions | suggest_formula() | None |
| Wilkinson reference card | FORMULA_REFERENCE_CARD | None |

### 2.7 Pipeline and Sandbox

| Feature | files_for_reference | statistics |
|---------|---------------------|------------|
| Multi-step pipeline | run_pipeline (tool_call, code, formula, transform, condition) | None |
| Safe code execution | execute_code (sandbox) | None |

---

## 3. Migration Candidates

### 3.1 Full Migration (copy with minimal adaptation)

| File | Target | Notes |
|------|--------|-------|
| `formula_dsl.py` | `aiecs/tools/statistics/formula_dsl.py` or `aiecs/tools/statistics/utils/formula_dsl.py` | Standalone; no server state. Add to statistics package. |
| `table_formatter.py` | `aiecs/tools/statistics/table_formatter.py` or `aiecs/tools/statistics/utils/table_formatter.py` | Standalone; pure functions. |
| `descriptive_stats.py` | `aiecs/tools/statistics/descriptive_stats.py` | Can be used by data_profiler_tool. |
| `advanced_stats.py` | `aiecs/tools/statistics/advanced_stats.py` | Can be used by statistical_analyzer_tool. |
| `data_cleaner.py` | `aiecs/tools/statistics/data_cleaner.py` | Can be used by data_transformer_tool. |

### 3.2 Adapted Migration (refactor for BaseTool / stateless use)

| File | Target | Adaptation |
|------|--------|------------|
| `data_loader.py` | Merge into `data_loader_tool.py` or add as `statistics/loaders/spss_loader.py` | Extract `load_file`, `_load_spss`, `_load_parquet`, `_load_csv`; add apply_labels, custom_headers, metadata to data_loader_tool. |

### 3.3 Deferred (not in initial migration)

| File | Reason |
|------|--------|
| `pipeline.py` | Depends on server state (df, meta, custom_headers); design defers stateful sessions. |
| `sandbox.py` | Code execution adds security surface; defer to later phase. |
| `server.py` | MCP entry point; our server is main_mcp.py. |

### 3.4 Reference Only (do not migrate)

| File | Reason |
|------|--------|
| `README.md` | Documentation. |
| `pyproject.toml` | Package config. |

---

## 4. Summary

- **File correspondence:** 4 partial overlaps (data_loader, data_profiler, data_transformer, statistical_analyzer); 2 statistics-only (data_visualizer, model_trainer); 5 files_for_reference-only (table_formatter, formula_dsl, data_cleaner, descriptive_stats, advanced_stats as standalone modules; pipeline, sandbox, server).
- **Missing features:** SPSS metadata/labels, custom headers, tabulate output, formula DSL, custom cleaning rules, ANCOVA/factor analysis, pipeline, sandbox.
- **Migration priority:** formula_dsl, table_formatter, descriptive_stats, advanced_stats, data_cleaner (full or adapted). data_loader enhancements (SPSS metadata, custom_headers). Defer pipeline and sandbox.
