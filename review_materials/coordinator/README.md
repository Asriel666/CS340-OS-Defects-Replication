# 协调人对照材料

`author_labels.csv` 来自作者公开标签的既有证据清单，只在两位审核者交回独立判断之后使用。它不应随盲审表一同发送。仓库整体是公开的，这种文件分离只能降低无意看到答案的风险，独立填写仍依赖实际操作。

在仓库根目录运行：

```powershell
py -3.11 scripts/manage_review.py prepare
py -3.11 scripts/manage_review.py check
```

`prepare` 只创建缺失文件，拒绝样本变化，不覆盖已有判断。`check` 检查两份 `blind/reviewer_*.csv` 的样本、类别代码、姓名、日期和证据，并将状态写到 `results/human_review/status.json`。空表输出 `pending_human_review`，一致率为 `null`，不会将空白算成吻合。

每条记录完整填写三个维度（允许 `unconfirmed`）、姓名、日期和理由，且确认判断有证据链接时，才计为已提交记录。两人都填齐只会得到 `ready_for_adjudication`，不是“人工复核已完成”。工具无法证明身份、独立性或证据真实性。

仲裁时保存 A/B 原判断、分歧、采用的标签与依据、实际参加者和日期，再将结论同步到本地 `data/review/rq123_label_review.csv`。该文件及旧版表中的已有人工内容由协调人核对，程序不会自动覆盖。生成的状态不替代人工仲裁记录。
