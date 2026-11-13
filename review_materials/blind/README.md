# 独立审核者材料

协调人只向审核者分发本目录中的 `cases.csv`、本说明及该审核者对应的 `reviewer_A.csv` 或 `reviewer_B.csv`。判断前不要打开另一位审核者的文件、`coordinator/`、旧版审核表或其他含作者标签的材料。公开仓库无法强制隔离答案，此处通过分开发放减少提前看到答案的风险。

每位审核者阅读 12 条样本的原始报告和补丁，独立填写三个维度，记录姓名、日期、具体证据链接与判断理由。HTTP 200 可能只是登录页，必须确认页面实际包含补丁或缺陷描述。无法取得材料、内容不足或无法判断的维度填写 `unconfirmed`，在 `notes` 中写明原因。

## 填写列

| 列 | 填写要求 |
|---|---|
| `reviewer`, `os`, `bug_id`, `patch_url` | 保留预置值；补充来源放在 `evidence_urls` |
| `reviewer_name` | 实际审核者姓名，同一份表由同一人填写 |
| `reviewed_on` | 实际审核日期，格式 `YYYY-MM-DD` |
| `your_os_layer` | 下列系统层次代码之一，或 `unconfirmed` |
| `your_affected_function` | 下列功能代码之一，或 `unconfirmed` |
| `your_trigger_scenario` | 下列触发代码之一，或 `unconfirmed` |
| `evidence_urls` | 支撑判断的具体公开链接，多个链接以空格或分号分隔 |
| `notes` | 简短说明判断依据；未确认时说明缺失什么证据 |

判定过程应结合缺陷描述和代码上下文。类别名称只提供共同词表，不代表原论文已给出无歧义的操作化定义；遇到边界情况保留不确定性，不能仅按文件名硬套标签。

| 维度 | 合法代码与含义 |
|---|---|
| 系统层次 | `Kernel` 内核；`SystemLib` 系统库；`RuntimeVM` 运行时/虚拟机；`Framework` 框架；`SystemService` 系统服务；`Application` 应用 |
| 受影响功能 | `Mem/Res Mng` 内存/资源；`Pro/Tas Sch` 进程/任务调度；`Sto Mng` 存储；`Dev/Drv` 设备/驱动；`Net/Com` 网络/通信；`Com/Adp` 兼容/适配；`Sec/Perm` 安全/权限；`Gra/Ren` 图形/渲染 |
| 触发场景 | `Per/Ide Dep` 权限/身份依赖；`Reg Ope` 常规操作；`Bor Con` 边界条件；`Con/Mul Thr` 并发/多线程；`Sta Dep` 状态依赖；`Env Dep` 环境依赖；`Mul/Loc Dep` 多语言/本地化依赖 |

完成后分别交回表格，由协调人保存原始版本，再共同讨论分歧并对照作者标签。明确无法确认的格不计入一致率的分母。即使两人相同，也不自动等同于作者标签正确或已完成仲裁。
