param(
    [Parameter(Mandatory = $false)]
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'

$problemTitles = @{
    '2021-A' = 'FAST主动反射面的形状调节'
    '2021-B' = '乙醇偶合制备C4烯烃'
    '2021-C' = '生产企业原材料的订购与运输'
    '2022-A' = '波浪能最大输出功率设计'
    '2022-B' = '无人机遂行编队飞行中的纯方位无源定位'
    '2022-C' = '古代玻璃制品的成分分析与鉴别'
    '2023-A' = '定日镜场的优化设计'
    '2023-B' = '多波束测线问题'
    '2023-C' = '蔬菜类商品的自动定价与补货决策'
    '2024-A' = '板凳龙'
    '2024-B' = '生产过程中的决策问题'
    '2024-C' = '农作物的种植策略'
    '2025-A' = '烟幕干扰弹的投放策略'
    '2025-B' = '碳化硅外延层厚度的确定'
    '2025-C' = 'NIPT的时点选择与胎儿的异常判定'
}

$sourcePdfs = @{
    '2021-A' = '2021\2021年_A题_FAST主动反射面的形状调节.pdf'
    '2021-B' = '2021\2021年_B题_乙醇偶合制备C4烯烃.pdf'
    '2021-C' = '2021\2021年_C题_生产企业原材料的订购与运输.pdf'
    '2022-A' = '2022\2022年_A题_波浪能最大输出功率设计.pdf'
    '2022-B' = '2022\2022年_B题_无人机遂行编队飞行中的纯方位无源定位.pdf'
    '2022-C' = '2022\2022年_C题_古代玻璃制品的成分分析与鉴别.pdf'
    '2023-A' = '2023\2023年_A题_定日镜场的优化设计.pdf'
    '2023-B' = '2023\2023年_B题_多波束测线问题.pdf'
    '2023-C' = '2023\2023年_C题_蔬菜类商品的自动定价与补货决策.pdf'
    '2024-A' = '2024\2024年_A题_板凳龙.pdf'
    '2024-B' = '2024\2024年_B题_生产过程中的决策问题.pdf'
    '2024-C' = '2024\2024年_C题_农作物的种植策略.pdf'
    '2025-A' = '2025\2025年_A题_烟幕干扰弹的投放策略.pdf'
    '2025-B' = '2025\2025年_B题_碳化硅外延层厚度的确定.pdf'
    '2025-C' = '2025\2025年_C题_NIPT的时点选择与胎儿的异常判定.pdf'
}

$recordTemplates = @{
    '00-任务状态.md' = @'
# 任务状态

- 当前阶段：未开始
- 允许资料：题目、附件、方法库、非当年写作参考
- 禁止资料：互联网、当年答案、当年优秀论文、管理员映射
- 最近一次更新：
- 下一步：
'@
    '01-题目理解.md' = @'
# 题目理解

## 已知条件与数据

## 目标与评价指标

## 逐问重述

## 变量、符号与单位

## 歧义、缺失信息与必要假设

## 题间依赖关系
'@
    '02-逐问建模.md' = @'
# 逐问建模

每一问独立建立以下小节；后续问题若依赖前问，明确写出接口变量和误差传播路径。

## 第 1 问

### 候选方案

### 选型理由

### 模型定义与假设

### 求解算法

### 风险与替代方案
'@
    '03-求解与验证.md' = @'
# 求解与验证

## 数据预处理审计

## 代码、参数与运行环境

## 逐问结果

## 正确性检查

## 敏感性、稳定性与误差分析

## 失败尝试及其可迁移教训
'@
    '04-结果与论文.md' = @'
# 结果与论文

## 关键结论

## 模型优点与局限

## 摘要草稿

## 正文结构

## 图表清单

## 可复现材料清单
'@
    '05-优秀论文复盘.md' = @'
# 优秀论文揭晓后复盘

此文件只能在盲解提交冻结后填写。

## 对照材料清单

## 结论差异

## 建模思路差异

## 数据处理与算法差异

## 写作与图表差异

## 自己方案中应保留的创新

## 应修正的问题及证据

## 下一轮可执行改进
'@
    '06-更新记录.md' = @'
# 更新记录

每次修改追加一条，禁止覆盖旧记录。

| 日期 | 阶段 | 修改文件 | 修改原因 | 新证据 | 影响范围 | 是否更新总经验 |
|---|---|---|---|---|---|---|
'@
}

foreach ($category in 'A', 'B', 'C') {
    foreach ($year in 2021..2025) {
        $key = "$year-$category"
        $problemDir = Join-Path $Root "题库\$($category)题\$year"
        $processDir = Join-Path $problemDir '解题过程'
        $attachmentTarget = Join-Path $problemDir '附件'
        New-Item -ItemType Directory -Force -Path $processDir, $attachmentTarget | Out-Null

        Copy-Item -LiteralPath (Join-Path $Root $sourcePdfs[$key]) -Destination (Join-Path $problemDir '题目.pdf') -Force
        $attachmentSource = Join-Path $Root "$year\附件_$($category)题"
        if (Test-Path -LiteralPath $attachmentSource) {
            Copy-Item -Path (Join-Path $attachmentSource '*') -Destination $attachmentTarget -Recurse -Force
        }

        $problemReadme = @"
# $year 年 $category 题

- 题目：$($problemTitles[$key])
- 正式题面：``题目.pdf``
- 数据附件：``附件/``
- 独立解题记录：``解题过程/``
- 本题沉淀经验：``经验.md``
- 当年优秀论文仅可在盲解冻结后放入：``揭晓后参考/``
"@
        Set-Content -LiteralPath (Join-Path $problemDir 'README.md') -Value $problemReadme -Encoding utf8

        foreach ($template in $recordTemplates.GetEnumerator()) {
            $target = Join-Path $processDir $template.Key
            if (-not (Test-Path -LiteralPath $target)) {
                Set-Content -LiteralPath $target -Value $template.Value -Encoding utf8
            }
        }

        $experiencePath = Join-Path $problemDir '经验.md'
        if (-not (Test-Path -LiteralPath $experiencePath)) {
            Set-Content -LiteralPath $experiencePath -Encoding utf8 -Value @'
# 本题经验

## 可复用方法

## 容易误判的信号

## 数据与代码陷阱

## 验证清单

## 不应泛化的结论

## 向总经验提出的候选更新
'@
        }
        New-Item -ItemType Directory -Force -Path (Join-Path $problemDir '揭晓后参考') | Out-Null
        $keep = Join-Path $problemDir '揭晓后参考\.gitkeep'
        if (-not (Test-Path -LiteralPath $keep)) {
            New-Item -ItemType File -Path $keep | Out-Null
        }
    }
}
