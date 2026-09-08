import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile, Workbook } from "./.artifact-runtime/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const scriptPath = fileURLToPath(import.meta.url);
const root = path.resolve(path.dirname(scriptPath), "..", "..", "..");
const sourcePath = path.join(root, "工作记录", "诊断结果", "Q03", "q03_design_output_v001.json");
const outputPath = path.join(root, "工作记录", "结果", "Q03", "第3问测线设计-v001.xlsx");
const diagnosticDir = path.join(root, "工作记录", "诊断结果", "Q03");
const auditPath = path.join(diagnosticDir, "q03_excel_audit_v001.json");

const model = JSON.parse(await fs.readFile(sourcePath, "utf8"));
const lines = model.final.lines;
const candidates = model.candidate_comparison;
const workbook = Workbook.create();
const summary = workbook.worksheets.add("摘要");
const lineSheet = workbook.worksheets.add("测线设计");
const candidateSheet = workbook.worksheets.add("候选比较");
for (const sheet of [summary, lineSheet, candidateSheet]) sheet.showGridLines = false;

summary.getRange("A2:B2").values = [["第3问最终测线设计摘要", null]];
summary.getRange("A4:B11").values = [
  ["指标", "数值"], ["方案", model.final.name], ["测线条数", model.final.line_count],
  ["区域内总长度/m", model.final.total_length_m], ["区域内总长度/km", model.final.total_length_km],
  ["正式重叠率最小值/%", model.final.min_eta_previous * 100],
  ["正式重叠率最大值/%", model.final.max_eta_previous * 100], ["漏测面积/m²", model.final.missing_area_m2],
];
summary.getRange("A2:B2").format.font = { name: "Arial", size: 15, bold: true, color: "#0F172A" };
summary.getRange("A4:B4").format = { fill: "#164E63", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" } };
summary.getRange("A5:B11").format.font = { name: "Arial", size: 10, color: "#0F172A" };
summary.getRange("A5:A11").format.font.bold = true;
summary.getRange("B7:B8").format.numberFormat = "0.00";
summary.getRange("B9:B10").format.numberFormat = "0.0000";
summary.getRange("B11").format.numberFormat = "0.00";
summary.getRange("A4:B11").format.borders = { preset: "outside", style: "thin", color: "#94A3B8" };
summary.getRange("A:A").format.columnWidth = 25;
summary.getRange("B:B").format.columnWidth = 38;

const headers = [
  "测线编号", "西向东序号", "方向", "方向角/°", "起点x/m", "起点y/m", "终点x/m", "终点y/m",
  "区域内长度/m", "横坐标/海里", "水深/m", "与前线间距/m", "坡面覆盖宽度/m", "有符号重叠/m",
  "正式重叠率/%", "当前宽度口径/%", "覆盖左界x/m", "覆盖右界x/m",
];
const rows = lines.map((row) => [
  row.line_id, row.order_west_to_east, row.direction, row.direction_deg_from_east_ccw,
  row.start_x_m, row.start_y_m, row.end_x_m, row.end_y_m, row.length_inside_m,
  row.x_nmi, row.depth_m, row.spacing_from_previous_m, row.width_slope_m, row.signed_overlap_m,
  row.overlap_rate_previous === null ? null : row.overlap_rate_previous * 100,
  row.overlap_rate_current === null ? null : row.overlap_rate_current * 100,
  row.left_x_m, row.right_x_m,
]);
const lineEnd = 4 + rows.length;
lineSheet.getRange("A2:R2").values = [["第3问逐线正式设计", ...Array(17).fill(null)]];
lineSheet.getRange("A4:R4").values = [headers];
lineSheet.getRange("A5").write(rows);
lineSheet.getRange("A2:R2").format.font = { name: "Arial", size: 14, bold: true, color: "#0F172A" };
lineSheet.getRange("A4:R4").format = { fill: "#164E63", font: { name: "Arial", size: 9, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
lineSheet.getRange("A5:R" + lineEnd).format.font = { name: "Arial", size: 9, color: "#0F172A" };
lineSheet.getRange("B5:B" + lineEnd).format.numberFormat = "0";
lineSheet.getRange("D5:D" + lineEnd).format.numberFormat = "0.0";
lineSheet.getRange("E5:R" + lineEnd).format.numberFormat = "0.0000";
lineSheet.getRange("A4:R" + lineEnd).format.borders = { preset: "outside", style: "thin", color: "#94A3B8" };
lineSheet.getRange("A:R").format.columnWidth = 14;
lineSheet.getRange("C:C").format.columnWidth = 18;
lineSheet.freezePanes.freezeRows(4);

const candidateHeaders = ["候选", "目标重叠率/%", "可行", "条数", "总长度/m", "正式最小/%", "正式最大/%", "当前口径最小/%", "当前口径最大/%"];
const candidateRows = candidates.map((row) => [
  row.candidate, row.target_eta * 100, row.feasible ? "是" : "否", row.line_count, row.total_length_m,
  row.min_eta_previous * 100, row.max_eta_previous * 100, row.min_eta_current * 100, row.max_eta_current * 100,
]);
const candidateEnd = 4 + candidateRows.length;
candidateSheet.getRange("A2:I2").values = [["候选设计比较", ...Array(8).fill(null)]];
candidateSheet.getRange("A4:I4").values = [candidateHeaders];
candidateSheet.getRange("A5").write(candidateRows);
candidateSheet.getRange("A2:I2").format.font = { name: "Arial", size: 14, bold: true, color: "#0F172A" };
candidateSheet.getRange("A4:I4").format = { fill: "#164E63", font: { name: "Arial", size: 9, bold: true, color: "#FFFFFF" }, wrapText: true, horizontalAlignment: "center" };
candidateSheet.getRange("A5:I" + candidateEnd).format.font = { name: "Arial", size: 9, color: "#0F172A" };
candidateSheet.getRange("B5:B" + candidateEnd).format.numberFormat = "0.0000";
candidateSheet.getRange("E5:I" + candidateEnd).format.numberFormat = "0.0000";
candidateSheet.getRange("A:I").format.columnWidth = 18;
candidateSheet.getRange("A:A").format.columnWidth = 32;
candidateSheet.getRange("A4:I" + candidateEnd).format.borders = { preset: "outside", style: "thin", color: "#94A3B8" };

workbook.recalculate();
for (const [sheetName, fileName] of [
  ["摘要", "第3问设计摘要-预览-v001.png"], ["测线设计", "第3问逐线设计-预览-v001.png"], ["候选比较", "第3问候选比较-预览-v001.png"],
]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1.4, format: "png" });
  await fs.writeFile(path.join(diagnosticDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
const inspection = await workbook.inspect({ kind: "workbook,sheet,region,formula", maxChars: 20000, tableMaxRows: 8, tableMaxCols: 18 });
await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const reloaded = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const lineRange = reloaded.worksheets.getItem("测线设计").getRange("A4:R" + lineEnd);
const values = lineRange.values;
const formulas = lineRange.formulas;
const errorPattern = /#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A/;
const errorCount = values.flat().filter((value) => errorPattern.test(String(value ?? ""))).length +
  formulas.flat().filter((value) => errorPattern.test(String(value ?? ""))).length;
const audit = {
  sheets: reloaded.worksheets.items.map((sheet) => sheet.name),
  line_count: values.length - 1,
  header_count: values[0].length,
  key_first_line: values[1],
  key_last_line: values[values.length - 1],
  formula_error_count: errorCount,
  all_passed: values.length - 1 === 34 && values[0].length === 18 && errorCount === 0,
  inspection,
};
await fs.writeFile(auditPath, JSON.stringify(audit, null, 2), "utf8");
console.log(JSON.stringify({ all_passed: audit.all_passed, line_count: audit.line_count, sheets: audit.sheets }, null, 2));
if (!audit.all_passed) throw new Error("Question 3 workbook audit failed");

