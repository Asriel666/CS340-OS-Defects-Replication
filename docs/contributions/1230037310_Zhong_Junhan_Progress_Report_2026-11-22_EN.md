# Personal Contributions and Progress Report by Zhong Junhan (1230037310)

**Student ID: 1230037310**

**Name: Zhong Junhan**

**Report date: 22 November 2026**

This report documents my registered contributions and the project's progress for course assessment. The historical contribution list is fixed at commit `0c949b3a326c2a7e8d6198ae949cf8bb25fe9b27`, covering work submitted through 18 November. The synchronization check at the start of the 22 November session found no subsequent team updates. The new work described in Section 7 was committed and pushed as [d0c43ca](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/d0c43ca6919c459103329fb31fa94d7b422448a6) at approximately **14:28 Beijing time on 22 November**, changing 26 files. This English version translates and revises the report; it does not represent another round of experiments.

The personal contributions below are registered under my student ID and follow tasks I requested, with Codex assistance. Codex contributed to implementation, computation, automated verification, source inspection, and documentation. These activities are distinguished from independent student annotation and execution. Git records establish submitted changes and their registered identity, but do not establish hours worked or a numerical share of individual effort. No actual working hours are inferred here.

## 1. Project Objectives and Current Results

*Toward Understanding Operating System Defects* is an empirical study of Android, Linux, and HarmonyOS defects. It investigates category distributions, relationships between classification dimensions, and similarities across systems. Our replication uses the authors' 1,500 released labels to recompute the principal statistics and produce runnable code, comparisons, a report, and presentation materials. The original 15-page paper has been archived with [source information and hashes](../../papers/README.md). [Reading notes with original page references](../paper_reading_notes.md) explain its methods and findings.

| Scope | Current result | Interpretation |
|---|---|---|
| RQ1, Table II | 114/114 match | All five classification dimensions covered |
| RQ2, Tables III–V | 438/438 match | Totals and both margins checked for nine joint matrices |
| RQ3, fixed complete categories | 8/9 match | Android–HarmonyOS triggers remain approximately 0.61 versus the paper's 0.38 |
| RQ3, pairwise removal of shared zeros | 9/9 match at two decimals | A compatible explanation, not an author-confirmed method |
| Figures 2/3 sensitivity analysis | One tested convention matches 39/39 | Supplementary team analysis; original binning code remains unconfirmed |
| Figure 4(d), Overall | None of 42 candidates reproduces it | Input, aggregation, and inconsistent pair labeling require clarification |

The core comparison covers **552 table values and nine independent coefficients: 561 items, with 560 matches**. Numerical coverage is 100% of the planned core and the match rate is approximately 99.8%. Neither percentage measures completion of the entire paper or course project. Repeated exploratory comparisons are excluded from this denominator.

Code, reports, and a ten-slide editable presentation are available. Independent student judgments, a student-operated clean rerun, and presentation rehearsals remain outstanding. An approximate 85%–90% overall completion estimate reflects these remaining deliverables, rather than a measured score. See the [full replication report](../reproduction_report.md) and [core summary](../../results/full/stage_summary.json).

## 2. Registered Contributions and File Evidence

The following five historical commits contain `1230037310` in their messages and list `ZHONGJUNHAN` as Git author. The first 14 November commit identifies `Zhong Junhan` in its message body. Dates below are **Git commit dates in Beijing time, not push timestamps**. The [contribution CSV](../../results/contributions/1230037310/commit_history.csv) and [JSON](../../results/contributions/1230037310/commit_history.json) retain complete messages, hashes, dates, and file lists.

| Date and commit | Substantive contribution | Representative evidence | Files changed |
|---|---|---|---:|
| 6 Nov, [adcaba4](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/adcaba47d05c664ed87ba32f7174b59b2cd0dc39) | Added RQ2/RQ3 calculations, independent paper references, execution options, tests, results, and reporting to the existing RQ1 pipeline | [Joint analysis](../../src/osdefects/joint.py), [similarity](../../src/osdefects/similarity.py), [verification](../../scripts/verify_reproduction.py) | 72 |
| 12 Nov, [1d6fc52](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/1d6fc524487c1810d1c6f23973f72337c63c63ce) | Synchronized team results, checked execution, narrowed binning claims, and corrected the denominator describing censored-data effects | [Weekly record](../weekly/2026-11-12.md), [methods appendix](../methods_appendix.md) | 4 |
| 14 Nov, [1cc01d0](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/1cc01d005080d720e9c6af341a73a19011c4a854) | Added category-set sensitivity, patch-content auditing, separated review forms, presentation materials, and validation evidence | [Category analysis](../../src/osdefects/category_policy.py), [patch audit](../../scripts/audit_review_evidence.py), [review workflow](../../src/osdefects/review_workflow.py) | 65 |
| 14 Nov, [c91ba25](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/c91ba2533908a2571e1dc0fa3611172593cd3bde) | Archived the paper, provenance and hashes, and prepared reading notes with page references | [Paper provenance](../../papers/source.json), [reading notes](../paper_reading_notes.md) | 5 |
| 18 Nov, [0c949b3](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/0c949b3a326c2a7e8d6198ae949cf8bb25fe9b27) | Fixed Week 2 repository and reference paths; added regression tests, clean-run evidence, and a completion checklist | [Entry point](../../run_weekend_02.py), [tests](../../tests/test_weekend_02.py), [verification](../../results/weekend_02/verification.json) | 39 |

File counts include generated CSV, JSON, logs, and figures; they do not measure individual effort. File links show the current repository version, while each commit page identifies the exact historical change. The 22 November commit is documented separately in Section 7 so that the five-commit historical export remains reproducible against its fixed baseline.

### Team Contributions and Attribution

My registered work builds on the team's repository. Other members' submissions remain attributed to them:

- **Asriel / ZHONG YIHENG, 1240008428:** [0a711e3](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/0a711e399b3f93d5c9c43e6031736bfcd0e73c25) supplied early data extraction and OS-layer replication. [fbf0b34](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/fbf0b34452bcede130253f650429c327c3a2bb48) supplied the Week 2 entry point and historical outputs. My 18 November contribution repaired and verified that entry point.
- **HAOXUAN-stack / GUO HAOXUAN, 1230036051:** [c6b0fcb](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/c6b0fcb69ce341e68994edfbb9d445b00d437932) added repair-size sensitivity; [16a69c1](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/16a69c15d4ed73f22b9e0cd7d50a862a1c0e91c1) added Figure 4 exploration and the 184-record anomaly checklist; [924f3f6](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/924f3f6fa0effb68477d26476544933d104243e3) prepared the initial review materials. My subsequent contributions extended the category policy, inspected patch content, and protected the review workflow.

The existing team identity in `SUBMISSION.json` is preserved. Final joint attribution and the actual division of student work still require agreement among members.

## 3. Fixed Data, Statistical Methods, and Methodological Findings

The authors' data are pinned to commit `832d536f5d381d428a887e59ceeacc90a40e3b7e`. After newline normalization, the file contains **766,561 bytes** and has SHA-256 `3794ff8c39e975ff457f264cb863f6e191297614dc0273f04c09ac654962eed5`. The program parses JSON arrays from the HTML without executing its JavaScript. It checks 500 records per system, unique IDs within each system, recognized labels, and valid numerical structures. [Input provenance](../../results/full/source_provenance.json) records the source and verification method.

For RQ1, the first four dimensions are single-label classifications whose percentages each sum to 100%. Code elements are multilabel: every category still uses 500 defects as its denominator, so percentages need not sum to 100%. For RQ2, each cell is its count divided by 500, rather than a row-normalized proportion. Blank cells explicitly omitted as zeros in the paper are treated as zero, and category names determine alignment. RQ3 aligns category vectors, assigns average ranks to ties, and computes Pearson correlation between ranks: standard Spearman correlation.

The key additional finding concerns **categories that are zero in both compared systems**. Android and HarmonyOS both have zero `Mul/Loc Dep` triggers, while Linux has one. Keeping all seven categories gives `0.6126374746329801`. Removing this pair's shared-zero category gives `0.3768511731740915`, displayed as 0.38. Three policies generate 27 comparisons and 189 rows of category evidence, with an optional SciPy cross-check. The earlier 144-case exploration did not include pairwise exclusion. The 14 November update corrected the overly broad claim that such alternatives had already been ruled out. See the [category-policy analysis](../category_policy_analysis.md).

For Figures 2/3, the matching candidate uses left-closed, right-open bins, includes the final upper endpoint, places zeros in the first bin, and assigns censored values using their lower bounds. A correction on 12 November distinguished the number of affected records from affected bars: seven of fourteen records in HarmonyOS's final function-count bin are censored, but changing their treatment affects **one of twelve function-count bars**. Matching the plotted values does not establish which script the authors used.

## 4. Patch Evidence and Human Review Status

The fixed sample uses seed 340 to select twelve cases, four per system. On 14 November, eight Android/Linux links yielded readable diffs, while four HarmonyOS links returned Gitee login pages. HTTP 200 alone therefore did not demonstrate readable patch evidence. The four missing patches were obtained from public mirrors on 22 November, bringing cumulative availability to **12/12**. The earlier eight were not downloaded again in that session.

Content inspection identified specific questions. Linux 2063344 showed conditional-macro changes, locally supporting its zero-function count. Linux 2044546 included function-body changes despite a recorded count of zero. Android A-323850943 changed function bodies in two files despite a recorded count of one. Official CVE metadata marked CVE-2023-52756 as `REJECTED` without explaining the specific reason, which does not justify deleting the sample. The authors' data remain unchanged. Evidence is preserved in the [audit report](../review_evidence_audit.md) and [audit JSON](../../results/review_evidence/audit.json).

The review workflow separates author labels into a coordinator file and stores A/B judgments independently. It validates sample membership, labels, evidence, reviewer identity fields, and dates, while preserving existing entries. The [human-review status](../../results/human_review/status.json) still records **0/12 for both A and B**, with no calculated agreement rate. Automated retrieval and assisted interpretation do not complete those reviews, and the full 184-record anomaly checklist has not been individually verified.

## 5. Week 2 Entry-Point Repair and Historical Validation

The original Week 2 launcher incorrectly located the repository's parent directory and reference file. Even `--help` failed with a missing-module error. The 18 November repair allows execution from another working directory and retains strict input hashing. Historical `weekend_02/` outputs remain intact; new outputs use `results/weekend_02/`.

The historical source hash equals the verified input with one additional trailing LF. This explains the byte-level difference without relaxing verification. It does not establish how the historical file was originally downloaded.

Historical evidence records **109 passing tests on 14 November**, followed by **112 on 18 November** after three entry-point regressions were added. The latter validation exercised offline execution with plots, a fresh online download, and offline execution from an external working directory. Each successful scenario performed three calculations and matched all 114 Table II values. A deliberately incorrect input hash was rejected.

The seven figures from this supplementary entry point do not add RQ2/RQ3 coverage or replace the exact-bar sensitivity analysis of Figures 2/3. Details appear in the [18 November record](../weekly/2026-11-18.md). These counts belong to their historical runs; Section 7 records the newer validation. Repeated calculations demonstrate deterministic execution on fixed input, not independent sampling or proof of correct author labels.

## 6. Reproduction Commands and Assessment Materials

Use global Python 3.11 as described in the [README](../../README.md). Numerical checks can skip plotting dependencies. A separate working copy is recommended; use `--offline` only after obtaining a valid cache.

```powershell
py -3.11 -m unittest discover -s tests -v
py -3.11 scripts/run_stage.py --analysis all --runs 3 --no-plots --output-dir work/ta_core
py -3.11 scripts/run_category_policy.py --runs 3 --offline
py -3.11 run_weekend_02.py --offline --no-plots --output-dir work/ta_week2
py -3.11 scripts/manage_review.py check
```

The consolidated validation command creates temporary clean copies and requires network access for the fixed data download:

```powershell
py -3.11 scripts/verify_reproduction.py --output-dir results/checkpoint_2026-11-22 --allow-source-changes
```

Section 7 explains the narrow purpose of `--allow-source-changes`. The English PDF can be rebuilt from this Markdown report with the following PowerShell command:

```powershell
py -3.11 scripts/build_progress_report.py --language en
```

The builder accepts `--font` and `--bold-font` when alternate installed fonts are needed. Detailed comparisons are available in the [RQ1 CSV](../../results/full/tables/table_ii.csv), [RQ2 CSV](../../results/full/tables/joint_comparison.csv), and [RQ3 CSV](../../results/full/tables/similarity_comparison.csv). The [full report](../reproduction_report.md), [ten-slide presentation](../../presentations/defense_2026-11-14_v2.pptx), and [speaker notes](../../presentations/speaker_notes.md) explain the results. Every presentation page was rendered and inspected; there is no completed student rehearsal record.

## 7. Work Completed and Verified on 22 November

Commit [d0c43ca6919c459103329fb31fa94d7b422448a6](https://github.com/Asriel666/CS340-OS-Defects-Replication/commit/d0c43ca6919c459103329fb31fa94d7b422448a6), pushed at approximately **14:28 Beijing time**, contains the following work across **26 changed files**. It is additional to the five historical commits listed in Section 2. Its recorded Git commit time is 14:28:01; push verification is a separate observation.

### 7.1 Public-Mirror Evidence for Four HarmonyOS Patches

The new [read-only mirror checker](../../scripts/check_review_mirrors.py) made 21 source requests. All four original Gitee URLs still returned login pages, but GitHub's `openharmony/kernel_linux_5.10` repository supplied substantive patches. Three commits matched the original full SHA. CVE-2024-46740's twelve-character prefix resolved to `60351db082d82f1f673b5e2ab5e9366a3bb98c1b`. The original Gitee site did not independently supply its full SHA, so the prefix limitation remains explicit.

For each case, the checker compared the API response, a separately requested `.patch`, and the current and parent file contents. Commit and parent identifiers, changed-file lists, addition/deletion counts, Git blob hashes, and patch blob prefixes agreed. The [source JSON](../../results/review_evidence_followup/sources.json) and [21-request CSV](../../results/review_evidence_followup/sources.csv) preserve URLs, timestamps, statuses, byte counts, and response hashes. Raw third-party responses remain in ignored local storage. No patch was applied or executed.

Two findings followed from reading these patches. **CVE-2023-52756 changes only enumeration definitions outside function bodies**, supporting its recorded zero-function count. **CVE-2024-46740 contains one added line and no deleted lines**, whereas the released data report `line_changes=2`. The latter remains a discrepancy under the usual additions-plus-deletions definition, without changing the dataset. The [follow-up report](../review_evidence_followup_2026-11-22.md) provides case-specific evidence.

A [supplementary source list](../../review_materials/blind/supplemental_sources_2026-11-22.csv) contains links and identity details without author labels. The cumulative twelve readable cases combine the earlier eight with these four; human A/B reviews remain zero.

### 7.2 Output Protection and Consolidated Verification

The Week 2 entry point now rejects output locations that could overwrite source code, historical outputs, core results, or another analysis. It also rejects nonempty directories lacking its own analysis identifier. Checks run before downloading or writing. Empty directories and recognized Week 2 output directories remain usable, and the statistical formulas are unchanged.

The consolidated verifier now includes Week 2 fresh downloads, offline invocation from an external directory, and corrupted-cache rejection. It retains six core scenarios, category-policy checks, and empty-review workflow checks. Temporary copies are compared with published numerical results and input hashes, and their source files must exactly match the current checkout.

New scripts and tests naturally differ from the historical 14 November source snapshot. Explicit `--allow-source-changes` permits only that historical source-manifest difference and records added, changed, and missing files. Reference baselines, fixed-input hashes, published values, and current-source copy consistency remain strict. Historical environment records were preserved rather than overwritten to create artificial agreement.

At **14:23:06 Beijing time on 22 November, all 134 unit tests passed**, an increase of 22 over 18 November. Six core scenarios, category-policy analysis, and two Week 2 scenarios each performed three calculations: **nine scenarios and 27 calculations**. Additional checks covered empty review forms, corrupted-cache rejection, and the file signatures of seventeen historical core figures. Numerical reruns used `--no-plots`; this session did not redraw or visually recheck all those figures. See the [verification record](../../results/checkpoint_2026-11-22/verification.json).

An earlier full attempt stopped at the Week 2 fresh download because of a TLS EOF error. The entire verification was retried from new temporary directories, with no intervening changes to code, data, or TLS settings, and passed. Both outcomes are recorded in the [attempt history](../../results/checkpoint_2026-11-22/attempts.json).

### 7.3 Contribution Archive and Reporting Materials

The [contribution exporter](../../scripts/export_contributions.py) matches the complete student ID in commit titles or bodies and preserves original messages, authors, dates, full hashes, and file lists. Its fixed-baseline export contains the five historical commits. Regression tests cover Unicode names, empty bodies, IDs appearing only in a body, and similar-number false matches.

The submitted Chinese report includes editable Markdown and a paginated PDF with source links, supported by the [report builder](../../scripts/build_progress_report.py). The [22 November weekly record](../weekly/2026-11-22.md) gathers new findings, validation, and remaining tasks. This English report provides the same evidence and attribution in English, with the completed commit identified explicitly; translation does not increase the experiment or test counts.

## 8. Remaining Work and Next Steps

The remaining priorities require actual student participation. Two members should independently read the twelve case reports and patches, record their judgments, and preserve disagreements and discussion evidence. One member should personally run the project from a clean directory and record their name, date, commands, and results. Each presenter should rehearse once, and members should confirm joint attribution.

A practical scheduling estimate is 1.5–2.5 hours per person for sample review, followed by approximately 2–3 combined person-hours for discussion, execution, and presentation practice: roughly **5–8 person-hours remaining**. These are planning estimates, not hours already worked.

The authors' actual shared-zero policy, binning script, and Overall definition remain unresolved methodological limits. The [draft questions for the authors](../author_questions.md) have not been sent. Completion should focus on explaining the available evidence, reproducing the calculations, and documenting genuine student review, without expanding the task into reconstructing and relabeling all 1,500 records.
