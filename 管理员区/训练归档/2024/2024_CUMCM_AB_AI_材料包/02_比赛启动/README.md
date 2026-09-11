# 数学建模竞赛 AI 材料包：启动核心

## 这是什么

本目录是“下次比赛可直接上传给 AI”的流程核心。它把规则核验、独立求解、证据冻结、官方案例比较、原创性与最终提交变成可检查的闸门，并提供统一的机器输出协议和八周训练计划。

本目录本身只是“比赛启动核心”，不含某道题的答案。完整材料包另在 `03_A题_独立成果`、`04_B题_独立成果`和 `05_官方范例对比` 保存 2024 A/B 题的训练成果。新比赛开始时不应把这些历届答案纳入首轮上传，应按包根目录 `upload_profiles.json` 的 `competition_start_minimal` 配置使用。

## 文件说明

| 文件 | 用途 | 是否直接上传给 AI |
|---|---|---|
| `MASTER_PROMPT.md` | 中文比赛启动主提示词；定义角色、禁止事项、G0–G9 闸门、工作循环与首轮回复 | 是，优先上传 |
| `output_protocol.schema.json` | JSON Schema Draft 2020-12；约束来源、假设、数据血缘、模型、运行、结果、验证、AI 合规、原创性和产物 | 是 |
| `output_protocol.example.json` | 只演示协议格式；明确没有真实题目和结果 | 是；不得复制占位内容为结果 |
| `training_plan.md` | 八周训练计划、指标口径、每周任务与放行条件 | 训练时上传或供队伍执行 |
| `training_plan.json` | 同一训练计划的机器可读版本 | 需要自动记分/生成看板时上传 |
| `UPLOAD_CHECKLIST.md` | 开赛上传、独立冻结、参考比较和最终提交的阻断清单 | 是，开赛与赛末各核对一次 |

## 推荐的完整材料包结构

下图是便于跨项目理解的**逻辑布局**；实际开赛上传与 AI 交互时，以 `MASTER_PROMPT.md` 定义的 `00_rules`--`07_audit` 数字目录为准。可按角色一一映射，例如 `rules/current` → `00_rules`、`inputs/raw` → `01_inputs`、`knowledge_base` → `02_knowledge`、`independent` → `03_independent`、`references/official` → `04_reference`、`comparison` → `05_comparison`、`submission` → `06_submission`、`audit` → `07_audit`。

```text
competition_ai_pack/
  starter/                         # 本目录
  knowledge_base/                  # 自包含、无答案的方法知识库
    INDEX.md
    modeling_cards/
    coding_and_validation/
    writing_and_submission/
  rules/current/                   # 当届官方规则与 AI 条款
  inputs/raw/                      # 题面、附件、空白模板，只读
  inputs/inputs_manifest.json
  independent/A/                   # A 题独立论文、代码、结果、测试、日志
  independent/B/                   # B 题独立论文、代码、结果、测试、日志
  independent/freeze_manifest.json # G6 冻结哈希
  references/official/             # G6 后、规则允许时取得的官方案例
  comparison/                      # 盲评、差异与重新验证后的经验
  training/                        # 实际训练记录，不覆盖计划
  submission/                      # 最终候选提交物
  audit/                           # output_protocol、AI 日志、验证报告
```

自包含知识库应解释“何时用、何时不用、输入输出、假设、验证、反例和实现陷阱”，避免只罗列算法名。它可以吸收经重新推导的通用经验，但不得包含可直接复现某届答案的数值、范文段落或来源不明代码。

## 开赛使用顺序

### 1. 本地准备

1. 复制一份完整材料包到新项目；原始题面、附件和模板保存只读副本。
2. 从主办方官方网站取得**当届**规则、AI 条款与提交说明，保存原文件/网页快照、URL、时间和 SHA-256。
3. 填写 `MASTER_PROMPT.md` 顶部参数；未知项写 `待核验`，不猜。
4. 按 `UPLOAD_CHECKLIST.md` 完成 A、B 部分；有 `[BLOCK]` 未通过时停止外传或检索。
5. 为全部初始文件生成 `inputs_manifest.json`，再上传提示词、schema、知识库、规则、题面、附件和空白模板。

### 2. 独立求解

让 AI 从 G0 开始，每过一闸门生成一份 `output_protocol.json`。独立阶段允许的知识仅限：题面、官方数据/模板、当届规则、无答案通用知识库和队伍自行生成的文件。

不得在 G6 前搜索、上传或打开答案、优秀论文、解题文章/视频、代码仓库或搜索摘要。需要验证数值时，应先用解析基线、穷举、另一实现、可信通用库、步长/容差加密和边界测试。

### 3. 冻结

G6 至少包含：独立论文、源代码、配置、依赖锁、原始/派生结果、提交模板、测试、验证、失败日志、AI 使用日志、协议 JSON 和完整 SHA-256 清单。冻结版设为只读或版本标签；后续修改另起版本。

### 4. 官方案例比较

只有当 G0 与 G6 已通过、当届规则允许且队员明确授权，才能切换到参考比较。优先且默认只使用赛事官网/主办方正式发布的案例；找不到应记录 `not_found`，不得由聚合站替代“官方”。

先用同一评分表分别盲评独立稿和案例，再比较：

- 建模：问题拆解、变量/状态、假设、识别性、模型选择与敏感性；
- 写作：摘要信息密度、公式定义、图表同源、验证可见性、局限与引用；
- 编程：数据契约、算法复杂度、根/优化/仿真稳定性、测试与复现；
- 完成思路：选题、分工、阶段交付、失败接管、冻结和提交检查。

每条改变标明 `验证缺口触发`、`案例启发` 或 `独立优化`。案例启发的内容必须重新推导、独立实现和验证，并保留来源；不得覆盖独立冻结版或把案例数值写成自有结果。

## 协议使用规则

`output_protocol.schema.json` 采用 JSON Schema 2020-12。真实记录从 `output_protocol.example.json` 的**结构**开始，但必须：

- 将 `synthetic_example` 改为 `false`；
- 替换示例竞赛、占位模型和 `unavailable` 结果，不复制示例说明为证据；
- 使用项目根目录相对路径和小写 64 位 SHA-256；
- 用 ID 将来源、假设、血缘节点、模型、运行、结果、验证和产物互相连接；
- 只把已执行且有证据的检查标为 `pass`；未知为 `not_run` 或开放问题；
- JSON 不使用注释、尾逗号、`NaN` 或 `Infinity`。

在当前中文材料包根目录，建议至少做两层校验：

```powershell
python -m json.tool "02_比赛启动/output_protocol.schema.json" > $null
python -m json.tool "06_审计/output_protocol.json" > $null
```

若环境已安装支持 Draft 2020-12 的 `jsonschema`：

```powershell
python -c "import json, pathlib; from jsonschema import Draft202012Validator, FormatChecker; s=json.loads(pathlib.Path('02_比赛启动/output_protocol.schema.json').read_text(encoding='utf-8')); d=json.loads(pathlib.Path('06_审计/output_protocol.json').read_text(encoding='utf-8')); Draft202012Validator.check_schema(s); Draft202012Validator(s, format_checker=FormatChecker()).validate(d); print('schema+instance: PASS')"
```

解析通过只表示 JSON 合法；schema 通过只表示结构满足协议，均不证明数学结论正确。仍需运行 `validations` 中登记的实质检查，并核对引用的证据文件确实存在。

## 训练计划怎么落地

`training_plan.json` 是只读基准，实际观测另存 `training/training_actuals.json`。第一周测量本队写作基线 `B`，后续用相对比率而不是套用陌生队伍的绝对字数。复现率保存整数分子/分母；覆盖率的分母来自显式需求表；分支覆盖无法测量时写 `not_measured`，不得猜数。

每周未过门槛先补最弱项 2–4 小时再测。速度未达标但质量、复现、验证和赛时限通过，可以记 `quality_pass_speed_warning`；不得为追写作速度删去验证或隐瞒问题。

## 最低材料清单

一次可投入比赛的完整包至少应有：

- 本 `02_比赛启动/` 的六类核心文件（复制到新比赛项目后可命名为 `starter/`）；
- 自包含知识库及索引；
- 当届规则、AI 条款、题面、附件、空白模板与输入哈希清单；
- A/B 或所选题的独立论文、代码、配置、依赖、结果和提交表；
- 单元/集成/边界/收敛/敏感性/独立复算证据；
- 冻结清单、AI 使用日志、输出协议、引用清单和最终上传回执；
- 若做参考比较：官方案例来源清单、盲评记录、影响登记和重新验证证据。

## 四条红线

1. 不照抄或近似改写范文，不把范文数值回填为独立答案。
2. 不伪造数据、运行、引用、测试、来源、AI 使用或队员确认。
3. 不把题面外假设、默认参数、容差和失败案例藏在代码里。
4. 不忽略当届 AI 使用规则；未核验时按受限模式工作并请求人工确认。
