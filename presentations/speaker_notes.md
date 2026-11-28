# 操作系统缺陷论文复现答辩讲解稿

报告人：1230037310 钟峻瀚。基于团队仓库成果，Codex 协助编写。

## 第 1 页：操作系统缺陷研究论文复现与方法核查

本报告介绍团队仓库的当前复现结果。报告人是 1230037310 钟峻瀚。原作者发布了 1,500 条标签，团队仓库重新计算统计结果，Codex 协助实现、验证、材料整理和本演示文稿。不能将团队结果表述为报告人独立完成全部代码或重新标注。共同署名与实际分工仍需成员确认。

来源：https://arxiv.org/html/2608.20643v1
https://github.com/Asriel666/CS340-OS-Defects-Replication
仓库：docs/reproduction_report.md、docs/weekly/2026-11-14.md。

## 第 2 页：数据来源与复现范围

本次复现使用作者已发布的标签，Android、Linux、HarmonyOS 各 500 条。通过固定 Git 提交和 SHA-256 摘要锁定输入，程序仅解析 JSON 数组，不执行网页 JavaScript。RQ1 是五个单维分布，RQ2 是三个联合分布，RQ3 是三个维度上的系统对相似度。表格百分比以每个系统 500 条为分母。Linux 样本包括 Ubuntu 生态，三个系统的采样渠道不同，结果只描述该样本，不能直接评价操作系统质量。

来源：https://github.com/zuohongyao/zuohongyao.github.io/blob/832d536f5d381d428a887e59ceeacc90a40e3b7e/index.html
https://arxiv.org/html/2608.20643v1#S4
仓库：results/full/source_provenance.json、results/full/data_validation.json。

## 第 3 页：RQ1：五维分类分布全部吻合

单维比例等于具有该标签的缺陷数量除以 500。五个维度分别有 6、8、7、5、12 类，对三个系统共比较 114 个百分比，全部吻合。前四维为单标签，因此各自合计 100%。代码元素是多标签，分母仍为 500，类别比例之和可以超过 100%。右侧只展示系统层次的最大类别，不等于全部缺陷都在这些层。

来源：https://arxiv.org/html/2608.20643v1#S4.T2
仓库：results/full/tables/table_ii.csv、results/full/tables/univariate_summary.json。

## 第 4 页：RQ2：三组联合分布全部吻合

联合分布单元格用该格缺陷数除以该系统全部 500 条，而不是进行行归一化。三个系统下的每张矩阵总计 500，行列边际与 RQ1 一致。Table III 是 6×8，三个系统共 144 项。Table IV 是 6×7，共 126 项。Table V 是 8×7，共 168 项。右侧三个例子对应 143、198、179 条，分母均是 500。共现结果不能作为因果结论。

来源：https://arxiv.org/html/2608.20643v1#S4.T3
https://arxiv.org/html/2608.20643v1#S4.T4
https://arxiv.org/html/2608.20643v1#S4.T5
仓库：results/full/tables/joint_comparison.csv、results/full/tables/joint_summary.json。

## 第 5 页：RQ3：固定类别下 8 / 9 个系数吻合

标准 Spearman 等于两个计数向量各自取升序平均秩后，再算秩的 Pearson 相关。三个维度按固定类别顺序对齐，并列值取平均秩。该页列出全部 9 个独立系统对，镜像单元格与对角线不重复计数。唯一差异是触发场景 Android 与 HarmonyOS，论文 0.38，固定七类重算 0.6126374746329801。下一页检查这一差异的可能方法原因，但不追溯性地修改预先声明的核心口径。

来源：https://arxiv.org/html/2608.20643v1/heatmap-a.png
https://arxiv.org/html/2608.20643v1/heatmap-b.png
https://arxiv.org/html/2608.20643v1/heatmap-c.png
仓库：results/full/tables/similarity_comparison.csv、reference/similarity_baselines.json。

## 第 6 页：共同零类别给出可检验的候选解释

新增检验只改变两个系统比较时使用的类别集合，不改原始标签，也不改平均秩 Spearman。下表最后一类 Mul/Loc Dep 在 Android 和 HarmonyOS 中都为零，但 Linux 该类有一条。因此移除“三系统全零类别”不会删除它。采用两系统非零类别的并集，即仅删除这两个系统共同为零的类别，向量从七维变六维，Spearman 从 0.6126374746329801 变为 0.3768511731740915，两位小数正好为 0.38。相同规则用于全部九对时得到 9/9 的数值相容，只有该对的结果变化。它是对差异的候选解释，不能证明原作者实际这样实现。核心固定类别的 8/9 记录仍保留。

来源：https://arxiv.org/html/2608.20643v1/heatmap-c.png
仓库：results/full/tables/univariate_summary.json、results/category_policy/、docs/category_policy_analysis.md。

## 第 7 页：Figures 2/3：39 个柱值有相容的候选口径

图 2 是修改行数，图 3 是涉及函数数和修改文件数。三组柱标签总共 39 个。已测试的候选中，左闭右开且最后一箱包含最终上界、零值计入第一箱、删失记录按下界归箱，可以 39/39 吻合。177 条函数数为零和 7 条带加号的下界记录使解释受到限制。HarmonyOS 最后函数数箱 14 条中 7 条为删失记录，保持未归属时该柱从 2.8% 变成 1.4%，其余 11 个函数数柱不变。不能因为一组假设完全吻合，就认定作者真的使用了同一脚本。Overall 的定义仍未确认，此页不纳入核心 561 项的完成率。

来源：https://arxiv.org/html/2608.20643v1/photo/group_changes.png
https://arxiv.org/html/2608.20643v1/photo/group_funcs.png
仓库：reference/figure_baselines.json、results/repair_size/tables/config_match_summary.csv、docs/methods_appendix.md。

## 第 8 页：运行与核验

助教可以从 README 安装全局 Python 3.11 的依赖，再用这一条命令运行三个研究问题、三次计算和图表。首次联网下载固定输入并检查摘要，已有合法缓存可离线复跑。单项 rq1、rq2、rq3 和旧 Stage 1 入口都保留。运行记录保留命令、环境、输入摘要、结果摘要以及逐项对比 CSV。测试覆盖数据摘要错误、重复 ID、未知标签、缺项基准、联合分布边际和 Spearman 并列秩。三次相同结果只说明固定输入下的执行稳定，不等于三次独立采样实验，也不能证明人工标签正确。最终测试数量和本轮复跑证据以当日周报为准。

来源：https://github.com/Asriel666/CS340-OS-Defects-Replication
仓库：README.md、results/full/verification.json、results/full/tables/repeated_run_statistics.csv、docs/weekly/2026-11-14.md。

## 第 9 页：12 条抽查：证据已整理，人工判断待完成

每个系统按缺陷 ID 排序，固定随机种子 340 抽 4 条，共 12 条。自动化核验已区分 HTTP 成功状态与真实补丁内容。Android 与 Linux 的 8 条获取到实质 diff，HarmonyOS 的 4 条原链接重定向至 Gitee 登录页，不能因为最终返回 200 就声称获得了补丁。盲审材料将作者标签放入 coordinator/author_labels.csv，与 reviewer_A.csv、reviewer_B.csv 分开。两位真实参与者分别阅读报告和补丁，填写系统层次、功能、触发场景及证据，随后保留分歧与仲裁依据。目前人工判断都未填写，因此不能报告标签一致率。缺少公开证据的条目允许标记未确认。另有 CVE-2023-52756 的官方记录为 REJECTED，撤回原因未说明，不等于代码没有缺陷，原数据保留。详见审计文档与 results/review_evidence/cve_sources.json。

仓库：docs/review_evidence_audit.md、review_materials/blind/reviewer_A.csv、review_materials/blind/reviewer_B.csv、review_materials/coordinator/author_labels.csv。

## 第 10 页：当前结论与下一步

当前可明确报告的核心结果是 552 个表格百分比全部吻合，9 个相关系数在固定类别下 8 个吻合。新增类别集合检验对原图 0.38 给出一个相容且可检验的解释，但作者方法仍未确认。下一步由两位实际参与者完成盲审并记录真实分工，然后进行答辩演练。需要作者澄清的问题已经具体化：Figure 4(c) 是否按系统对删除共同零类别，Figures 2/3 的分箱和删失处理，Figure 4(d) Overall 输入定义与系统对标注。任何对作者的联络都需要实际授权，本报告仅列出待确认事项，不表示已经发送询问。

来源：https://github.com/Asriel666/CS340-OS-Defects-Replication
仓库：docs/reproduction_report.md、docs/category_policy_analysis.md、docs/methods_appendix.md、docs/review_evidence_audit.md。
