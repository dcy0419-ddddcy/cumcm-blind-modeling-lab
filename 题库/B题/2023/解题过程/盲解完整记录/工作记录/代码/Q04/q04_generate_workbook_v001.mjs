import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile, Workbook } from "./.artifact-runtime/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const scriptPath = fileURLToPath(import.meta.url);
const root = path.resolve(path.dirname(scriptPath), "..", "..", "..");
const diagnosticDir = path.join(root, "工作记录", "诊断结果", "Q04");
const designPath = path.join(diagnosticDir, "q04_design_output_v001.json");
const verifyPath = path.join(diagnosticDir, "q04_verification_v001.json");
const outputPath = path.join(root, "工作记录", "结果", "Q04", "第4问测线设计-v001.xlsx");
const auditPath = path.join(diagnosticDir, "q04_excel_audit_v001.json");

const model = JSON.parse(await fs.readFile(designPath, "utf8"));
const verification = JSON.parse(await fs.readFile(verifyPath, "utf8"));
const workbook = Workbook.create();
const summary = workbook.worksheets.add("摘要");
const lineSheet = workbook.worksheets.add("测线设计");
const candidateSheet = workbook.worksheets.add("候选比较");
const verifySheet = workbook.worksheets.add("精度验证");
for (const sheet of [summary, lineSheet, candidateSheet, verifySheet]) sheet.showGridLines = false;

const finalEval = model.final_evaluations.bilinear_5m;
summary.getRange("A2:B2").values = [["第4问最终测线设计摘要", null]];
summary.getRange("A4:B17").values = [
  ["指标", "数值"],
  ["最终方案", model.selection.selected_name],
  ["选择准则", model.selection.criterion],
  ["测线总条数", model.final_design.line_count],
  ["南区纵向测线/条", model.final_design.blocks[0].lines.length],
  ["北区横向测线/条", model.final_design.blocks[1].lines.length],
  ["区域内总长度/m", finalEval.total_length_m],
  ["区域内总长度/km", finalEval.total_length_m / 1000],
  ["双线性5m漏测面积/m²", finalEval.missing_area_m2],
  ["双线性5m漏测率/%", finalEval.missing_percent],
  ["双线性5m超过20%重叠长度/m", finalEval.over20_pair_counted_length_m],
  ["三角网主对角5m漏测面积/m²", model.final_evaluations.tri_main_5m.missing_area_m2],
  ["三角网副对角5m漏测面积/m²", model.final_evaluations.tri_anti_5m.missing_area_m2],
  ["全部独立检查", verification.all_passed ? "通过" : "未通过"],
];
summary.getRange("A2:B2").format.font = { name: "Arial", size: 15, bold: true, color: "#0F172A" };
summary.getRange("A4:B4").format = { fill: "#164E63", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" } };
summary.getRange("A5:A17").format.font = { name: "Arial", size: 10, bold: true, color: "#0F172A" };
summary.getRange("B5:B17").format.font = { name: "Arial", size: 10, color: "#0F172A" };
summary.getRange("B8:B16").format.numberFormat = "0.000000";
summary.getRange("A4:B17").format.borders = { preset: "outside", style: "thin", color: "#94A3B8" };
summary.getRange("A:A").format.columnWidth = 35;
summary.getRange("B:B").format.columnWidth = 62;
summary.getRange("B5:B17").format.wrapText = true;

const lines = model.final_design.lines;
const lineHeaders = [
  "最终序号", "测线编号", "分区", "轴向", "航行方向", "方向角/°", "中心横向坐标/m",
  "起点x/m", "起点y/m", "终点x/m", "终点y/m", "区域内长度/m", "横向下界/m",
  "横向上界/m", "沿线下界/m", "沿线上界/m", "代表水深/m", "代表坡度/°",
];
const lineRows = lines.map((row) => [
  row.final_order, row.line_id, row.block, row.axis, row.direction, row.direction_deg_from_east_ccw,
  row.center_m, row.start_x_m, row.start_y_m, row.end_x_m, row.end_y_m, row.length_inside_m,
  row.cross_min_m, row.cross_max_m, row.along_min_m, row.along_max_m,
  row.representative_depth_m, row.representative_slope_deg,
]);
const lineEnd = 4 + lineRows.length;
lineSheet.getRange("A2:R2").values = [["第4问逐线正式设计", ...Array(17).fill(null)]];
lineSheet.getRange("A4:R4").values = [lineHeaders];
lineSheet.getRange("A5").write(lineRows);
lineSheet.getRange("A2:R2").format.font = { name: "Arial", size: 14, bold: true, color: "#0F172A" };
lineSheet.getRange("A4:R4").format = { fill: "#164E63", font: { name: "Arial", size: 9, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
lineSheet.getRange("A5:R" + lineEnd).format.font = { name: "Arial", size: 9, color: "#0F172A" };
lineSheet.getRange("A5:A" + lineEnd).format.numberFormat = "0";
lineSheet.getRange("F5:R" + lineEnd).format.numberFormat = "0.000000";
lineSheet.getRange("A4:R" + lineEnd).format.borders = { preset: "outside", style: "thin", color: "#94A3B8" };
lineSheet.getRange("A:R").format.columnWidth = 15;
lineSheet.getRange("B:B").format.columnWidth = 17;
lineSheet.getRange("C:E").format.columnWidth = 19;
lineSheet.freezePanes.freezeRows(4);

const candidates = model.candidate_metrics_coarse;
const candidateHeaders = ["候选方案", "漏测率/%", "超过20%重叠长度/m", "总长度/m", "总长度/km", "是否帕累托", "是否最终采用"];
const candidateRows = candidates.map((row) => [
  row.name, row.missing_percent, row.over20_pair_counted_length_m, row.total_length_m,
  row.total_length_m / 1000, model.pareto_names.includes(row.name) ? "是" : "否",
  row.name === model.selection.selected_name ? "是" : "否",
]);
const candidateEnd = 4 + candidateRows.length;
candidateSheet.getRange("A2:G2").values = [["第4问候选方案比较（20 m筛选）", ...Array(6).fill(null)]];
candidateSheet.getRange("A4:G4").values = [candidateHeaders];
candidateSheet.getRange("A5").write(candidateRows);
candidateSheet.getRange("A2:G2").format.font = { name: "Arial", size: 14, bold: true, color: "#0F172A" };
candidateSheet.getRange("A4:G4").format = { fill: "#164E63", font: { name: "Arial", size: 9, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", wrapText: true };
candidateSheet.getRange("A5:G" + candidateEnd).format.font = { name: "Arial", size: 9, color: "#0F172A" };
candidateSheet.getRange("B5:E" + candidateEnd).format.numberFormat = "0.000000";
candidateSheet.getRange("A4:G" + candidateEnd).format.borders = { preset: "outside", style: "thin", color: "#94A3B8" };
candidateSheet.getRange("A:A").format.columnWidth = 42;
candidateSheet.getRange("B:G").format.columnWidth = 22;

const checkRows = Object.entries(verification.checks).map(([name, row]) => [name, row.passed ? "通过" : "未通过", JSON.stringify(row)]);
const checkEnd = 4 + checkRows.length;
verifySheet.getRange("A2:C2").values = [["第4问独立验证清单", null, null]];
verifySheet.getRange("A4:C4").values = [["检查项", "结论", "审计摘要（JSON）"]];
verifySheet.getRange("A5").write(checkRows);
verifySheet.getRange("A2:C2").format.font = { name: "Arial", size: 14, bold: true, color: "#0F172A" };
verifySheet.getRange("A4:C4").format = { fill: "#164E63", font: { name: "Arial", size: 9, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
verifySheet.getRange("A5:C" + checkEnd).format.font = { name: "Arial", size: 8, color: "#0F172A" };
verifySheet.getRange("A5:C" + checkEnd).format.wrapText = true;
verifySheet.getRange("A4:C" + checkEnd).format.borders = { preset: "outside", style: "thin", color: "#94A3B8" };
verifySheet.getRange("A:A").format.columnWidth = 42;
verifySheet.getRange("B:B").format.columnWidth = 12;
verifySheet.getRange("C:C").format.columnWidth = 110;
verifySheet.getRange("5:" + checkEnd).format.rowHeight = 54;

workbook.recalculate();
for (const [sheetName, fileName] of [
  ["摘要", "第4问设计摘要-预览-v001.png"],
  ["测线设计", "第4问逐线设计-预览-v001.png"],
  ["候选比较", "第4问候选比较-预览-v001.png"],
  ["精度验证", "第4问精度验证-预览-v001.png"],
]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1.2, format: "png" });
  await fs.writeFile(path.join(diagnosticDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
const inspection = await workbook.inspect({ kind: "workbook,sheet,region,formula", maxChars: 24000, tableMaxRows: 8, tableMaxCols: 18 });
await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const reloaded = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const lineRange = reloaded.worksheets.getItem("测线设计").getRange("A4:R" + lineEnd);
const values = lineRange.values;
const formulas = lineRange.formulas;
const errorPattern = /#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A/;
const errorCount = values.flat().filter((value) => errorPattern.test(String(value ?? ""))).length
  + formulas.flat().filter((value) => errorPattern.test(String(value ?? ""))).length;
const audit = {
  sheets: reloaded.worksheets.items.map((sheet) => sheet.name),
  line_count: values.length - 1,
  header_count: values[0].length,
  key_first_line: values[1],
  key_last_line: values[values.length - 1],
  candidate_count: candidates.length,
  verification_check_count: checkRows.length,
  formula_error_count: errorCount,
  all_passed: values.length - 1 === 86 && values[0].length === 18 && candidates.length === 9
    && checkRows.length === 12 && verification.all_passed && errorCount === 0,
  inspection,
};
await fs.writeFile(auditPath, JSON.stringify(audit, null, 2), "utf8");
console.log(JSON.stringify({ all_passed: audit.all_passed, line_count: audit.line_count, sheets: audit.sheets }, null, 2));
if (!audit.all_passed) throw new Error("Question 4 workbook audit failed");
