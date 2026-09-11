# 2024 年全国大学生数学建模竞赛 B 题：独立解答复现说明

本目录是只依据原题形成的独立模型、程序和数值结果。没有使用、搜索或读取任何优秀论文、他人答案或参考解答。主报告为 `report_B_independent.md`。

## 目录结构

```text
B/
├─ report_B_independent.md       # 详细中文解题报告
├─ README.md                     # 本文件
├─ requirements.txt              # 最小 Python 依赖
├─ src/solve_b.py                 # 四问统一求解器
├─ tests/test_solver.py           # 关键边界、公式和最优策略单元测试
├─ results/                       # 程序自动生成的 CSV 与 JSON
└─ logs/run.log                   # 最近一次完整运行日志
```

## 环境与运行

已验证环境：Python 3.12.14、NumPy 2.3.5、Windows 11。程序只额外依赖 NumPy；CSV、JSON、枚举、日志和单元测试均使用标准库。

在 PowerShell 中执行：

```powershell
cd D:\2024\work_independent\B
python -m pip install -r requirements.txt
python src\solve_b.py
python -m unittest discover -s tests -v
```

若使用本机 Codex 捆绑环境，本次实际执行的是：

```powershell
$py = 'C:\Users\28717\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py src\solve_b.py
& $py -m unittest discover -s tests -v
```

完整求解约 10--15 秒（取决于 CPU）。固定随机种子使问题 4 的蒙特卡洛结果可复现。再次运行会更新 `results/` 中的同名结果和 `logs/run.log`。

## 策略编码

- 问题 2 的四位串依次为 `检测零件1、检测零件2、检测成品、拆解不合格成品`；1 表示“是”，0 表示“否”。例如 `1101` 表示检测两种零件、不检测成品、退回不合格品后拆解。
- 问题 3 采用 `xxxxxxxx/yyy/zzz/uv`：前 8 位为零件检测，随后 3 位为半成品检测、3 位为半成品拆解，最后两位为成品检测与成品拆解。
- 指标是“完成一份订单并最终交付合格品”的期望成本和期望利润。换货品不重复计销售收入；题目说明中的调换损失不包含替换品本身，而替换品的生产成本由更新方程另计。

## 结果文件

- `q1_boundaries.csv`：顺序检验每个累计样本量对应的接收/拒收边界。
- `q1_operating_characteristics.csv`：不同真实次品率下的精确停止概率和截断平均样本量。
- `q2_all_policies.csv`、`q2_optimal_policies.csv`：六种情形的全部 16 个策略及最优策略。
- `q3_all_feasible_policies.csv`、`q3_top20_policies.csv`：层级装配的 6012 个可行平稳策略及前 20 名。
- `q4_q2_posterior_all_policies.csv`、`q4_q2_posterior_selected.csv`：问题 2 的后验传播结果。
- `q4_q3_posterior_top20.csv`：问题 3 的后验前 20 名策略。
- `q4_sample_size_sensitivity.csv`：样本量 100、200、500 的敏感性结果。
- `summary.json`：适合程序读取的总结果与假设声明。

## 问题 4 的数据边界

原题只给出“次品率”，没有给出得到这些比例时的抽样量 `n` 和次品数 `x`，所以问题 4 不存在唯一的数值答案。本目录绝不把补设数据说成真实观测。为了展示完整计算，程序明确构造了一个带标签的示例情景：每个比例均来自 `n=100`，且 `x=n×题给比例`，再用 Jeffreys 先验 `Beta(0.5,0.5)` 更新并传播不确定性。样本量敏感性表说明结论如何随信息量变化。拿到真实记录后，应将 `beta_draws_for_nominal` 的输入替换为实际 `(n,x)`；其余优化流程不变。

## 模型适用范围

程序把检测视为无误差，缺陷相互独立，装配次品率指全部输入合格时仍由工序产生缺陷；检测位的含义是筛检“质量未知”的对象，已经检验合格且拆解中未受损的同一对象保持已知合格，无须无效复检。拆解后复用的是同一物理零件，因此若某个未检零件本身不合格，固定执行“拆解后仍不检测并复用”会以正概率永久循环，这类策略被标为不可行而不是偷偷把零件质量重新抽样。若实际工厂允许拆解后改用不同检测策略，可把“首次生产”和“返工状态”拆为不同状态，再做有限状态动态规划。

## 验证状态

- 完整求解器运行成功，全部 CSV/JSON 均由程序生成。
- `python -m unittest discover -s tests -v`：6 项测试全部通过。
- 问题 1 的边界误差用路径概率递推精确验证，不依赖蒙特卡洛。
- 问题 2 的 16 个策略全部枚举；问题 3 的 6012 个可行策略全部枚举。
- 问题 4 使用固定种子，且把蒙特卡洛次数、先验、样本情景写入结果文件。
