# 12 条补丁证据可读性审查确认（2026-11-28）

**审查人：1230036051 GUO HAOXUAN（HAOXUAN-stack）**。本页核对 12 条补丁证据的可读性并给出完成状态。

## 审查对象

README 入口区第 26 行记录：

> 11 月 14 日补丁正文审计：当时 8 条真实 diff、4 条登录页；11 月 22 日已补齐后四条公开镜像，累计 12/12 可读，人工审核仍待完成。

本次核验该声明的事实依据、统计口径与完成边界，并给出关闭/未关闭状态。

## 核验结论

| 审查项 | 状态 | 依据 |
|---|---|---|
| 补丁**证据可读性**（能否取得并交叉核验补丁正文） | **已完成（closed）** | 11-14 审计 8/12 + 11-22 镜像补证 4/4 = 12/12 |
| 两名学生的**人工标签审核**（独立重标注） | **未完成（open）** | A/B 盲审表判断列各 0/12；`data/review/rq123_label_review.csv` 0/12 |

两项是不同层面的证据：可读性审查是机器可完成的证据可得性核查；人工标签审核必须由真人独立填写，AI 预填判断属于伪造，本审查不做。

## 事实依据

**11 月 14 日审计**（[docs/review_evidence_audit.md](review_evidence_audit.md)、[results/review_evidence/audit.json](../results/review_evidence/audit.json)）：`sample_count=12`、`confirmed_diff_count=8`、`unconfirmed_count=4`、`human_reannotation_completed=false`。4 条未确认均为 Gitee 链接跳转登录页，HTTP 200 只证明服务器响应，不能证明正文可读。审计还登记了 2 项函数计数待澄清问题与 1 条 CVE 状态为 `REJECTED` 的来源事实，未改动作者数据。

**11 月 22 日补证**（[docs/review_evidence_followup_2026-11-22.md](review_evidence_followup_2026-11-22.md)、[results/review_evidence_followup/sources.json](../results/review_evidence_followup/sources.json)）：`samples=4`、`verified_public_patches=4`、`full_original_sha=3`、`original_prefix_resolved=1`。4 条均通过提交身份、父提交、变更文件清单、增删行数及当前/父版本 Git blob SHA-1 交叉核验；仓库为 `openharmony/kernel_linux_5.10`，未用同 CVE 的 Linux 上游提交替代 OpenHarmony fork 提交。

**累计口径**：8 + 4 = **12/12 可读**。这是跨两天的累计结果，不是同一天重新抓取全部 12 条；4 条 Gitee 原地址本次仍需登录，其中 `60351db082d8` 只在镜像侧由原 12 位前缀解析到完整提交，不宣称从原站独立获得完整 SHA。

**人工审核现状**（本轮只读核对）：`review_materials/blind/reviewer_A.csv` 与 `reviewer_B.csv` 的 `your_*` 判断列均为 **0/12 填写**，`data/review/rq123_label_review.csv` 的 reviewer A/B 字段同为 0/12。因此 README 中“人工审核仍待完成”的表述继续有效。

## 完成边界

- 本次确认仅关闭“补丁证据可读性”这一项，不关闭“人工标签审核”。
- 补丁可读、提交身份相符、计数相容，均不等于作者标签正确；本审查未重新裁定系统层次、受影响功能或触发场景。
- 未访问或执行任何补丁内容之外的操作，未修改作者数据、核心结果、A/B 表或旧审计文件。
- 网络证据有取回时点；未来来源不可访问时应重新核验，不能用旧缓存冒充本次成功。

## 复跑入口

```powershell
py -3.11 scripts/audit_review_evidence.py
py -3.11 scripts/check_review_mirrors.py
py -3.11 -m unittest discover -s tests
```

前两条会重新获取第三方来源并更新对应结果目录；离线测试只使用合成输入，不验证作者标签。
