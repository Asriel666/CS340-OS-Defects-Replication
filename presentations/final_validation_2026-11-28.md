# 最终版答辩 PPT 数值一致性审计

审计人：1230036051 GUO HAOXUAN（git 作者 HAOXUAN-stack）
审计日期：2026-11-28
被审文件：`presentations/OS_Defects_G15_Final_2026-11-27.pptx`（14 页，16:9）
机器可读结果：`presentations/final_validation_2026-11-28.json`

## 范围与边界

这是对**最终版 PPT 中可核对的数值断言**逐项对照仓库证据的检查，共 **17 项、17 项核实通过**。它不是人工标签复核，不是答辩演练，也不代表审计人独立重新跑过 PPT 制作流程。PPT 第 1 页列出的分工（Guo Haoxuan 负责 P7–P10 的批判性分析与结论/影响讲解；Zhong Yiheng 负责 P5–P6；Zhong Junhan 负责 P3–P4；Gu Xuanze 负责 P1–P2）按 PPT 原文照录，不改动他人署名。

## 核对结果

| PPT 页 | 断言 | 仓库出处 | 核对值 |
|---|---|---|---|
| P4 | Table II 114/114 吻合 | `results/full/tables/table_ii.csv` | 114/114 |
| P8 | 552/552 分布值吻合 | `table_ii.csv` + `joint_comparison.csv` | 114 + 438 = 552 |
| P6 | 8/9 相关系数吻合 | `results/full/tables/similarity_comparison.csv` | 8/9 |
| P6/P11 | 成对排除共享零后 9/9 | `results/category_policy/tables/category_policy_comparison.csv` | 9/9 |
| P6/P11 | A–H 触发场景 0.613 → 0.377 | 同上（pairwise_nonzero） | 0.3768511731740915 |
| P6/P11 | 完整类别 Spearman 0.6126 | `results/full/tables/similarity_summary.json` | 0.6126374746329801 |
| P9 | HarmonyOS 内核层 71.8% | `results/full/tables/table_ii.csv` | 71.8 |
| P4 | 64.8%–77.6% 改动 <30 行 | `results/repair_size/tables/convention_comparison.csv` | Android 64.8% / Linux 68.8% / HarmonyOS 77.6% |
| P4 | 76.8%–88.6% 涉及 1–3 文件 | `data/processed/records.json`（按 `modified_files` 重算） | Android 84.6% / Linux 76.8% / HarmonyOS 88.6% |
| P5 | Android 服务×权限触发 16.0% | `results/full/tables/joint_comparison.csv` | 16.0 |
| P5 | Linux 应用×环境依赖 29.8% | 同上 | 29.8 |
| P5 | HarmonyOS 内核×边界 39.6% | 同上 | 39.6 |
| P5 | HarmonyOS 内核×并发 19.4% | 同上 | 19.4 |
| P12 | 331 + 28 = 359，发布值 349 | `results/full/data_validation.json` | 异常保留 |
| P12 | 6 个 Unknown → Undecided；7 条下界 | `results/full/data_validation.json` | 均保留 |
| P1/P10 | Group 15 四位具名报告人 | PPT 第 1、10 页 | Guo Haoxuan / Zhong Yiheng / Zhong Junhan / Gu Xuanze |
| P6 | n=50：14 保持 / 9 改变 / 7 并列；53.3%；n=250：24/30 | `results/cross_os_similarity/summary.json`（sample_size_extension） | 14/9/7；(9+7)/30=53.3%；24/30 |

## 讲解时需要主动说明的三点

1. **0.38 是相容解释，不是作者确认的方法**。PPT P6/P11 的 0.3769 来自"按系统对排除共同零类别"，仓库 `category_policy_analysis.md` 已说明作者实际方法仍待确认；不要讲成"我们复现了作者的 0.38"。
2. **8/9 与 9/9 是两个不同口径**。固定完整类别是 8/9（核心 561 项中的那 1 项差异保留），成对排除共同零是 9/9 的候选解释。两个数字同时成立，不要混用。
3. **人工审核与演练仍未完成**。12 条抽查 A/B 表仍为空白，审计和数值核对不能替代真人阅读补丁或实际讲解。

本审计由自动化脚本对照仓库结果生成，PPT 其余非数值内容（结论判断、影响论述、图表视觉呈现）未逐条复核。
