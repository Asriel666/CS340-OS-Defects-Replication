# 操作系统缺陷论文核心结果复现报告

提交人：**1230036051 GUO HAOXUAN**

论文：[Toward Understanding Operating System Defects，arXiv:2608.20643v1](https://arxiv.org/html/2608.20643v1)

范围：使用作者公开的缺陷标签，重新计算 RQ1、RQ2、RQ3 的核心统计结果。

## 1. 当前成果与结论

本项目已实现并实际计算论文 Table II、Tables III–V 和 Figure 4(a–c) 的核心结果，共比较 **561 个不重复对比项：560 项吻合、1 项不吻合、0 项未确认**。其中表格百分比 552 项全部吻合，9 个跨系统相关系数中有 1 项存在差异。

| 研究问题 | 比较对象 | 比较项数 | 吻合 | 不吻合 | 未确认 | 核查入口 |
|---|---|---:|---:|---:|---:|---|
| RQ1：缺陷如何分布 | Table II，五个分类维度 | 114 | 114 | 0 | 0 | [逐项对比 CSV](../results/full/tables/table_ii.csv) |
| RQ2：不同维度如何关联 | Tables III–V，三组联合分布 | 438 | 438 | 0 | 0 | [逐项对比 CSV](../results/full/tables/joint_comparison.csv) |
| RQ3：不同系统有多相似 | Figure 4(a–c)，三维度各三个系统对 | 9 | 8 | 1 | 0 | [逐项对比 CSV](../results/full/tables/similarity_comparison.csv) |
| **核心结果合计** | **表格百分比与独立相关系数** | **561** | **560** | **1** | **0** | [机器可读总结果](../results/full/stage_summary.json) |

唯一不吻合项是 **Android–HarmonyOS 的触发场景 Spearman 相关系数**：本项目计算为 **0.6126374746329801**，论文 Figure 4(c) 标为 **0.38**。本项目保存输入、计算方法和原论文值，未通过修改标签或改变算法来追求吻合。

这里的“0 项未确认”仅指上述 561 个核心对比项。Figures 2/3 的新增敏感性分析在已测试候选中，以左闭右开（末箱含最终上界）、零值计入首箱、删失按下界的组合得到 39/39 吻合，见[方法核查附录](methods_appendix.md)。这仍待作者分箱脚本确证后才算精确复现；Figure 4(d) 的 Overall 计算以及人工标签复核仍未完成，均未混入核心完成率。

## 2. 数据来源与可追溯处理

输入来自作者公开的 1,500 条已标注缺陷：Android、Linux、HarmonyOS 各 500 条。数据固定在作者仓库提交 [`832d536f5d381d428a887e59ceeacc90a40e3b7e`](https://github.com/zuohongyao/zuohongyao.github.io/blob/832d536f5d381d428a887e59ceeacc90a40e3b7e/index.html)，运行时使用 SHA-256 验证输入文件。

程序只解析 HTML 内的 JSON 数据数组，不执行其中的 JavaScript。输入校验包括各系统记录数量、系统内缺陷 ID 唯一性、分类标签合法性以及数值字段结构。原始行保留在生成的数据文件中；规范化只做有记录的标签映射和类型转换。

论文基准与重新计算的结果分开保存：

- [RQ1 基准](../reference/paper_baselines.json)记录 Table II 的五维百分比及出处。
- [RQ2 基准](../reference/joint_baselines.json)直接从官方 HTML 的 Tables III–V 提取，按明确类别名称对齐到程序的固定顺序；保留论文原始行列顺序及来源摘要，没有使用数据集计算结果反填。
- [RQ3 基准](../reference/similarity_baselines.json)记录 Figure 4(a–c) 原图的数值、系统顺序和出处；矩阵对称位置只用于展示，不重复计入独立比较数量。

参考数组的类别顺序、形状、系统集合和值域均受到检查。缺失数组元素属于错误；若某个参考值确实无法确认，应显式保留未确认状态，不能以零或计算结果替代。

数据中的异常未被静默修复：保留 1 条增删行合计不一致、7 条函数数仅为下界、177 条涉及函数数为零的记录；6 条 HarmonyOS 严重性标签 `Unknown` 映射为论文的 `Undecided`，并保留原标签。详见[数据校验记录](../results/full/data_validation.json)及[方法核查附录](methods_appendix.md)。这些修复规模异常不参与本次分类计数。

## 3. RQ1：完整五维分布

对于每个系统和类别，比例计算为：

`该系统具有该类别标签的缺陷数量 / 500 × 100%`

系统层次、受影响功能、触发场景和严重性是单标签分类，各维度的类别比例合计应为 100%。代码元素是多标签分类，每个类别仍以该系统的 500 个缺陷为分母，各类比例之和可以超过 100%。

类别数分别为 6、8、7、5、12，乘以三个系统，共 **114 项**，全部与 Table II 吻合。

| 维度 | Android 的最大类别 | Linux 的最大类别 | HarmonyOS 的最大类别 |
|---|---|---|---|
| 系统层次 | SystemService，38.80% | Application，54.20% | Kernel，71.80% |
| 受影响功能 | Sec/Perm，60.00% | Com/Adp，41.20% | Mem/Res Mng，22.80% |
| 触发场景 | Bor Con，37.00% | Env Dep，62.00% | Bor Con，52.60% |
| 严重性 | High，91.00% | Undecided，65.20% | Medium，51.40% |
| 代码元素 | Call，63.40% | Assignment，54.40% | Call，61.80% |

这些结果描述作者筛选出的样本。不同系统的缺陷来源和严重性规则不同，因此不能据此直接给三个操作系统的质量排序。尤其 Linux 数据覆盖 Ubuntu 生态，不能把其 Application 比例解释为 Linux 内核自身的类别分布；`Undecided` 也不等于低严重性。

结果见[单维汇总](../results/full/tables/univariate_summary.json)。图表见[系统层次](../results/full/figures/rq1_os_layer.png)、[受影响功能](../results/full/figures/rq1_affected_function.png)、[触发场景](../results/full/figures/rq1_trigger_scenario.png)、[严重性](../results/full/figures/rq1_severity.png)、[代码元素](../results/full/figures/rq1_code_level.png)。

## 4. RQ2：三组联合分布

对于两个分类维度的每个交叉单元格，比例计算为：

`同时属于该行类别与该列类别的缺陷数量 / 500 × 100%`

分母是该系统的全部缺陷数量，因此每张联合表整体合计为 100%，并非每一行合计为 100%。每张表的计数总和必须为 500，行边际和列边际分别与独立计算的单维类别计数一致。

| 表格 | 行维度 × 列维度 | 每个系统的形状 | 三个系统的比较结果 |
|---|---|---|---|
| Table III | 系统层次 × 受影响功能 | 6 × 8 | 144/144 吻合 |
| Table IV | 系统层次 × 触发场景 | 6 × 7 | 126/126 吻合 |
| Table V | 受影响功能 × 触发场景 | 8 × 7 | 168/168 吻合 |

论文表头按与程序不同的顺序排列类别，提取时通过类别名称重排两个轴，避免按位置直接配对造成错误。三张论文表共 139 个空白格；各表注明确说明省略零值，所以这些空白格记录为零，未当作缺失值。

可用于课堂说明的三个具体结果为：

- Android 的“系统服务层 × 安全与权限”占全部缺陷 **28.60%**，对应 143 条。这里的 28.60% 不能解释为系统服务层内部占比。
- HarmonyOS 的“内核层 × 边界条件触发”占全部缺陷 **39.60%**，对应 198 条。
- Linux 的“兼容与适配 × 环境依赖触发”占全部缺陷 **35.80%**，对应 179 条。

九张联合矩阵的总数和双边际均通过检查，438 项均与论文一致。结果见[联合统计汇总](../results/full/tables/joint_summary.json)；代表性图表见 [Table III / Android](../results/full/figures/table_iii_Android.png)、[Table IV / HarmonyOS](../results/full/figures/table_iv_HarmonyOS.png)、[Table V / Linux](../results/full/figures/table_v_Linux.png)。

联合分布反映的是类别共现情况。本项目没有新增因果推断，也没有把单元格较大直接解释为某种系统设计必然导致缺陷。

## 5. RQ3：跨系统相似度与差异

RQ3 只比较论文 Figure 4(a–c) 使用的三个维度：系统层次、受影响功能、触发场景。每个维度先按相同类别顺序对齐各系统的计数向量，再计算标准 Spearman 相关系数：各向量取升序平均秩，再计算秩的 Pearson 相关。并列计数使用平均秩。

每个维度有三个独立系统对，共 **9 个系数**。对角线与镜像单元格不重复计数。完整精度结果保存在 CSV 和 JSON 中，对照论文显示精度时比较两位小数。

| 维度 | 系统对 | 论文值 | 本项目值（两位小数） | 状态 |
|---|---|---:|---:|---|
| 系统层次 | Android–HarmonyOS | -0.66 | -0.66 | 吻合 |
| 系统层次 | Android–Linux | 0.26 | 0.26 | 吻合 |
| 系统层次 | HarmonyOS–Linux | 0.09 | 0.09 | 吻合 |
| 受影响功能 | Android–HarmonyOS | 0.43 | 0.43 | 吻合 |
| 受影响功能 | Android–Linux | -0.19 | -0.19 | 吻合 |
| 受影响功能 | HarmonyOS–Linux | -0.52 | -0.52 | 吻合 |
| 触发场景 | Android–HarmonyOS | **0.38** | **0.61** | **不吻合** |
| 触发场景 | Android–Linux | 0.21 | 0.21 | 吻合 |
| 触发场景 | HarmonyOS–Linux | 0.41 | 0.41 | 吻合 |

以程序使用的固定触发类别顺序为例：

`Per/Ide Dep, Reg Ope, Bor Con, Con/Mul Thr, Sta Dep, Env Dep, Mul/Loc Dep`

| 系统 | 输入计数向量 |
|---|---|
| Android | `[156, 44, 185, 36, 74, 5, 0]` |
| HarmonyOS | `[14, 33, 263, 120, 56, 14, 0]` |

这两个向量得到 **0.6126374746329801**，与论文 **0.38** 相差约 **0.232637**。HarmonyOS 的两个 14 必须采用并列平均秩。将所有计数除以 500 转为比例不会改变秩，也不能解释这一差异。方法附录按论文显示顺序列出同一批计数；只要两个系统同步重排类别，计算结果相同。

当前证据能确定存在差异，但不能确定原因。需要作者提供原图实际使用的数据版本与脚本，才能判断是否涉及输入差异、图表誊录或算法口径。结果见[相似度汇总](../results/full/tables/similarity_summary.json)和[触发场景热力图](../results/full/figures/rq3_trigger_scenario.png)。

## 6. 运行方法与验证证据

使用全局 Python 3.11，依赖安装和绘图工具要求见 [README](../README.md)。从仓库根目录运行以下命令可完成核心统计、三次计算记录和图表生成：

```powershell
py -3.11 scripts/run_stage.py --analysis all --runs 3
```

已有经过校验的数据缓存时，可在新输出目录中离线复跑；缺少绘图依赖时可以只验证数值：

```powershell
py -3.11 scripts/run_stage.py --analysis all --runs 3 --offline --no-plots --output-dir work/ta_check
py -3.11 -m unittest discover -s tests -v
```

`--analysis rq1`、`rq2`、`rq3` 分别运行对应分析，`--analysis all` 运行全部核心分析。旧 `--stage 1` 入口保留原有 18 项系统层次统计；旧 `--all` 兼容参数不代表新的完整核心范围，检查完整结果应使用 `--analysis all`。

本次 47 项核心单元测试与 17 项敏感性分析测试（合计 64 项）全部通过；新目录中的六种实际运行场景（首次下载、离线全量、RQ1、RQ2、RQ3、旧 Stage 1）均通过，每种执行三次。测试覆盖错误摘要、重复 ID、未知标签、多标签分母、联合分布总数与边际、Spearman 并列秩、参考数组缺项、显式未确认值及分箱约定边界等场景。具体执行结果、命令和日志见[验证记录](../results/full/verification.json)。这是自动化新目录复跑，不代表另一名学生已完成独立操作。

| 证据文件 | 用途 |
|---|---|
| [stage_summary.json](../results/full/stage_summary.json) | 三个 RQ 的比较数量、状态、重复计算信息和人工复核状态 |
| [source_provenance.json](../results/full/source_provenance.json) | 数据 URL、固定提交、输入摘要和获取方式 |
| [environment.json](../results/full/environment.json) | 实际 Python、依赖版本及源文件摘要 |
| [repeated_run_statistics.csv](../results/full/tables/repeated_run_statistics.csv) | 三次实际计算各项结果的均值与标准差 |
| [verification.json](../results/full/verification.json) | 自动测试及隔离复跑的实际证据 |
| [figure_manifest.json](../results/full/figure_manifest.json) | 本次生成的全部图表清单 |

重复运行检查采用相同固定输入执行三次，比较语义结果摘要，并保留每次结果与日志。三次一致只能说明执行稳定，不能证明作者原始标注正确，也不是对样本不确定性的三次独立实验。

## 7. 人工复核、贡献边界与下一步

本次输入的 1,500 条标签来自原作者。Codex 协助完成了代码实现、基准整理、实际计算、自动化核验和本报告编写。提交人身份已记入 [SUBMISSION.json](../SUBMISSION.json)；本报告没有把自动生成的结果表述为两名学生分别完成的独立标注或个人代码贡献。

程序为人工检查生成 `data/review/rq123_label_review.csv`：每个系统按缺陷 ID 排序，以固定种子 340 抽取 4 条，共 12 条，预留 A、B 两位审核者的独立分类、证据、分歧处理和状态栏。该文件目前是**待人工填写模板**，不是审核完成证明；再次运行会保留已有填写内容，不覆盖人工记录。此路径在本地运行时生成，默认不作为已完成审查记录上传。

下一步应完成以下工作：

1. 由实际参与者独立阅读这 12 条缺陷的报告和补丁，核对系统层次、受影响功能、触发场景；填写证据链接和判断依据。打不开的材料记为未确认，不补造标签理由。
2. 对两份独立记录中的分歧进行讨论并保留原判断及最终依据，记录实际参与者与各自完成的工作。小样本抽查不能替代全部 1,500 条重新标注。
3. 继续核查 Figure 4(c) 的差异，优先取得作者的原始计算输入及脚本；原因未查明前保持当前不吻合记录。
4. 按“研究目标、数据与方法、RQ1、RQ2、RQ3、差异、局限、复现命令、实际分工”准备 8–10 页答辩 PPT，并由实际答辩者练习解释分母、多标签、并列秩和复现边界。PPT 与演练尚未计入本次完成项。

Figures 2/3 在已测试候选中有一组与全部柱标签吻合的处理：左闭右开（末箱含最终上界）、零值计入第一箱、删失记录按下界归箱。这里的吻合只证明相容，不能排除其他同箱赋值或证明作者实际使用了该脚本。HarmonyOS `10-50` 箱 14 条中有 7 条删失；改变删失归属只影响 1/12 个函数数柱值。作者的实际分箱脚本仍待确证，因此在作者确认前不宣称这两张图已精确复现。Figure 4(d) 的 Overall 输入定义不清，且图文对系统对的对应存在矛盾。相关证据与逐柱对比集中在[方法核查附录](methods_appendix.md)和 `results/repair_size/`。
