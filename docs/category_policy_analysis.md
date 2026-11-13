# RQ3 类别集合敏感性分析（2026-11-14）

这次补充实验找到了一个与论文 Figure 4(c) 数值相容的候选解释：**对每对系统，排除两边计数都为零的类别后，Android–HarmonyOS 的触发场景 Spearman 系数为 0.3768511731740915，按两位小数显示为 0.38。** 使用完整七类时仍为 0.6126374746329801，即 0.61。作者实际是否采用该规则尚未确认，原核心分析保留完整类别及 8/9 的比较结果。

## 分析设计与边界

这是发现原有差异后开展的**探索性敏感性分析**，并非事先注册的作者方法复现。数据仍是固定提交 `832d536f5d381d428a887e59ceeacc90a40e3b7e` 中的 1,500 条公开记录，未改变任何标签或分类计数。沿用原来的标准 Spearman 实现：先对选中的向量计算升序平均秩，再计算秩的 Pearson 相关系数。每个政策都覆盖论文使用的三个维度、九个独立系统对；没有只挑选发生差异的一对进行报告。

论文比较值来自现有的独立转录文件 [similarity_baselines.json](../reference/similarity_baselines.json)，原始来源为 [Figure 4(a)](https://arxiv.org/html/2608.20643v1/heatmap-a.png)、[Figure 4(b)](https://arxiv.org/html/2608.20643v1/heatmap-b.png) 和 [Figure 4(c)](https://arxiv.org/html/2608.20643v1/heatmap-c.png)。本实验不修改这些基准。

| 类别政策 | 明确规则 | 与论文吻合 | 不吻合 | 未确认 | 发生类别排除的系统对 |
|---|---|---:|---:|---:|---:|
| `fixed_all` | 保留所有规范类别，与原核心方法相同 | 8/9 | 1 | 0 | 0 |
| `global_nonzero` | 仅排除三个系统中计数都为零的类别 | 8/9 | 1 | 0 | 0 |
| `pairwise_nonzero` | 仅排除当前两个系统中计数都为零的类别 | 9/9 | 0 | 0 | 1 |

27 次比较是同一组九个论文系数在三个政策下的重复分析，**不能当作 27 个新的独立论文结果**。全局和成对政策不同：Linux 的 `Mul/Loc Dep` 计数为 1，因此全局政策保留该类别；Android 和 HarmonyOS 对应计数均为 0，成对政策才排除它。只有一边为零的类别在两种排除政策下都会保留。

## 发生变化的那一对

以下顺序始终固定，零计数表示公开数据中没有该类别记录，不被视为缺失值。

| 触发类别 | Android | HarmonyOS | Linux | 成对政策对 Android–HarmonyOS 的处理 |
|---|---:|---:|---:|---|
| Per/Ide Dep | 156 | 14 | 8 | 保留 |
| Reg Ope | 44 | 33 | 45 | 保留 |
| Bor Con | 185 | 263 | 95 | 保留 |
| Con/Mul Thr | 36 | 120 | 15 | 保留 |
| Sta Dep | 74 | 56 | 26 | 保留 |
| Env Dep | 5 | 14 | 310 | 保留 |
| Mul/Loc Dep | 0 | 0 | 1 | 两边同时为零，排除 |

完整向量及平均秩：

```text
Android counts    = [156, 44, 185, 36, 74, 5, 0]
HarmonyOS counts  = [14, 33, 263, 120, 56, 14, 0]
Android ranks     = [6, 4, 7, 3, 5, 2, 1]
HarmonyOS ranks   = [2.5, 4, 7, 6, 5, 2.5, 1]
rho               = 0.6126374746329801
```

成对排除最后一类后，**重新计算**平均秩：

```text
Android counts    = [156, 44, 185, 36, 74, 5]
HarmonyOS counts  = [14, 33, 263, 120, 56, 14]
Android ranks     = [5, 3, 6, 2, 4, 1]
HarmonyOS ranks   = [1.5, 3, 6, 5, 4, 1.5]
rho               = 0.3768511731740915
```

共享的零计数在完整向量中形成一对相同的最低秩。删除它会改变参与相关系数计算的类别集合和各秩的均值，因此结果变化；这不是更换 Spearman 算法或并列秩规则。其他八个系统对没有共同为零的类别，故数值完全不变。

## 全部九对结果

下表便于阅读而显示六位小数；[完整比较 CSV](../results/category_policy/tables/category_policy_comparison.csv) 保留 Python 浮点的完整可序列化精度、保留/排除类别、计数、平均秩、论文值、来源及逐项状态。

| 维度 | 系统对 | 论文 | 完整类别 | 全局非零 | 成对非零 |
|---|---|---:|---:|---:|---:|
| 层次 | Android–Linux | 0.26 | 0.257143 | 0.257143 | 0.257143 |
| 层次 | Android–HarmonyOS | -0.66 | -0.657143 | -0.657143 | -0.657143 |
| 层次 | Linux–HarmonyOS | 0.09 | 0.085714 | 0.085714 | 0.085714 |
| 功能 | Android–Linux | -0.19 | -0.190476 | -0.190476 | -0.190476 |
| 功能 | Android–HarmonyOS | 0.43 | 0.428571 | 0.428571 | 0.428571 |
| 功能 | Linux–HarmonyOS | -0.52 | -0.523810 | -0.523810 | -0.523810 |
| 触发 | Android–Linux | 0.21 | 0.214286 | 0.214286 | 0.214286 |
| 触发 | Android–HarmonyOS | 0.38 | **0.612637** | **0.612637** | **0.376851** |
| 触发 | Linux–HarmonyOS | 0.41 | 0.414431 | 0.414431 | 0.414431 |

## 运行与验证

在仓库根目录执行，使用已有的 SHA-256 校验缓存：

```powershell
py -3.11 scripts/run_category_policy.py --runs 3 --offline
```

没有缓存时省略 `--offline` 即会下载固定版本并校验。支持 `--output-dir` 指定独立结果目录。至少执行三次实际计算；每次重新读取记录、重新统计、重新选类并计算系数，三次结果的语义摘要必须相同。`--runs` 小于 3 会直接拒绝。

本次三次语义 SHA-256 均为：

```text
f6873aaeb7c8e68113de1145b358e0531806adbc576e442194b0c7284bebbded
```

这一检查证明执行稳定性，不证明原始标注或候选政策正确。运行时间、原始输入摘要、环境及代码摘要分别记录在 [run_summary.json](../results/category_policy/run_summary.json)、[runs](../results/category_policy/runs)、[source_provenance.json](../results/category_policy/source_provenance.json) 和 [environment.json](../results/category_policy/environment.json)。

还使用本机已有的 **SciPy 1.17.1** 对全部 27 个系数及平均秩进行了独立数值交叉核验，全部通过，系数绝对误差容限为 `1e-12`；见 [scipy_cross_check.json](../results/category_policy/scipy_cross_check.json)。这只独立核验已选择向量上的数值算法，不独立验证类别政策、标签或作者意图。SciPy 不是常规运行依赖；已有安装时可显式复查：

```powershell
py -3.11 scripts/run_category_policy.py --runs 3 --offline --cross-check-scipy
py -3.11 -m unittest discover -s tests -p test_category_policy.py -v
```

新增 12 项测试覆盖全局与成对排除的区别、单边零值保留、类别键对齐、缺项/多项拒绝、排除后空/单项/常量向量的未定义结果、并列平均秩、九对完整覆盖及原核心结果不变。除汇总比较外，[逐类别证据 CSV](../results/category_policy/tables/category_policy_evidence.csv) 共 189 行，明确标记每个政策下各类别是否保留。

## 应如何更新结论

可以说：**“完整类别定义得到 0.61；成对排除共同零类别得到 0.38，且这一统一政策与全部九个已发表系数在两位小数下吻合，因此类别集合选择是一个可核查的候选解释。”**

目前不能说作者确定采用了该政策，也不能仅凭吻合断定原图错误或原复现算法错误。这里没有证明三种政策穷尽所有可能解释。确认作者真实方法仍需要其原始代码、明确的方法说明或作者回应；不会因追求吻合而将核心分析改为成对排除。Overall 的合并定义、人工标注准确性、真实操作系统总体的可推广性仍不由本实验解决。
