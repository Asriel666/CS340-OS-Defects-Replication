"""One-factor extension: stratified sample-size sensitivity within the released corpus."""
from pathlib import Path
import random
import statistics
import math
from collections import defaultdict
from osdefects.common import OS_ORDER, write_csv, write_json
from osdefects.univariate import distribution


def total_variation(p, q):
    if len(p) != len(q):
        raise ValueError("Probability vectors must have equal lengths")
    if any(not math.isfinite(x) or not 0 <= x <= 1 for x in [*p, *q]):
        raise ValueError("Probabilities must be finite and lie between zero and one")
    if abs(sum(p)-1) > 1e-9 or abs(sum(q)-1) > 1e-9:
        raise ValueError("Total variation expects normalized probability vectors")
    return sum(abs(a-b) for a, b in zip(p, q))/2


def run_extension(records, reference, outdir, sizes=(50, 100, 250, 500), seeds=range(30)):
    outdir = Path(outdir)
    dimensions = ("os_layer", "affected_function", "trigger_scenario")
    rows = []
    for os_index, os_name in enumerate(OS_ORDER):
        corpus = sorted([r for r in records if r["os"] == os_name], key=lambda r: r["bug_id"])
        baseline = {}
        for dim in dimensions:
            categories = reference["dimensions"][dim]["categories"]
            _, percentages = distribution(corpus, dim, categories)
            baseline[dim] = [p/100 for p in percentages]
        for size in sizes:
            if not 1 <= size <= len(corpus):
                raise ValueError("Sample size outside available OS corpus")
            for seed in seeds:
                sample = random.Random(seed * 1009 + os_index).sample(corpus, size)
                for dim in dimensions:
                    categories = reference["dimensions"][dim]["categories"]
                    counts, percentages = distribution(sample, dim, categories)
                    p = [x/100 for x in percentages]
                    base = baseline[dim]
                    base_winners = {i for i, x in enumerate(base) if x == max(base)}
                    sample_winners = {i for i, x in enumerate(counts) if x == max(counts)}
                    if len(sample_winners) > 1:
                        outcome = "tie_in_draw"
                    elif len(base_winners) != 1:
                        outcome = "full_corpus_tie"
                    elif sample_winners == base_winners:
                        outcome = "same_unique"
                    else:
                        outcome = "different_unique"
                    rows.append({
                        "os": os_name, "dimension": dim, "sample_size": size, "seed": seed,
                        "total_variation": total_variation(p, base),
                        "same_unique_dominant_category": int(outcome == "same_unique"),
                        "dominant_category_outcome": outcome,
                    })
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["os"], row["dimension"], row["sample_size"])].append(row)
    aggregates = []
    for (os_name, dim, size), trials in grouped.items():
        values = [r["total_variation"] for r in trials]
        aggregates.append({"os": os_name, "dimension": dim, "sample_size": size, "trials": len(trials),
                           "tv_mean": statistics.mean(values), "tv_sd": statistics.stdev(values) if len(values)>1 else 0,
                           "dominant_retention_rate": statistics.mean(r["same_unique_dominant_category"] for r in trials)})
    by_seed = defaultdict(list)
    for row in rows:
        by_seed[(row["os"], row["sample_size"], row["seed"])].append(row["total_variation"])
    overall = []
    for os_name in OS_ORDER:
        for size in sizes:
            values = [statistics.mean(v) for (o,n,s),v in by_seed.items() if o==os_name and n==size]
            overall.append({"os":os_name,"sample_size":size,"trials":len(values),
                            "tv_mean_across_dimensions":statistics.mean(values),
                            "tv_sd_across_seeds":statistics.stdev(values) if len(values)>1 else 0})
    result = {"factor_changed": "Sample size per OS", "sizes": list(sizes), "seeds": list(seeds),
              "sampling": "Without replacement, independently within each OS; fixed seeds and fixed released labels.",
              "fixed": ["source commit", "taxonomy", "OS composition (equal per-OS sample size)", "analysis code", "hardware and software"],
              "limitation": "Internal robustness conditional on the released corpus; does not test external representativeness or annotation correctness.",
              "aggregates": aggregates,"overall_aggregates":overall}
    write_csv(outdir / "extension_trials.csv", rows)
    write_csv(outdir / "extension_summary.csv", aggregates)
    write_csv(outdir / "extension_overall_summary.csv", overall)
    write_json(outdir / "extension_summary.json", result)
    return result
