/** 问题 1：以附件 01 为模板生成、渲染并读回核验正式 Excel。 */

import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  FileBlob,
  SpreadsheetFile,
} from "./.artifact-runtime/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";


const scriptPath = fileURLToPath(import.meta.url);
const root = path.resolve(path.dirname(scriptPath), "..", "..", "..");
const sourcePath = path.join(root, "附件", "附件01.xlsx");
const modelPath = path.join(
  root,
  "工作记录",
  "诊断结果",
  "Q01",
  "q01_model_output_v001.json",
);
const outputDir = path.join(root, "工作记录", "结果", "Q01");
const versionedPath = path.join(outputDir, "result1-v001.xlsx");
const submissionPath = path.join(root, "result1.xlsx");
const previewPath = path.join(
  root,
  "工作记录",
  "诊断结果",
  "Q01",
  "result1-生成后预览-v001.png",
);
const auditPath = path.join(
  root,
  "工作记录",
  "诊断结果",
  "Q01",
  "q01_excel_audit_v001.json",
);


async function sha256(filePath) {
  const data = await fs.readFile(filePath);
  return crypto.createHash("sha256").update(data).digest("hex");
}


function normalizeCell(value) {
  return value === undefined ? null : value;
}


async function readRange(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const sheet = workbook.worksheets.getItemAt(0);
  const range = sheet.getRange("A1:J4");
  return {
    sheetName: sheet.name,
    values: range.values.map((row) => row.map(normalizeCell)),
    formulas: range.formulas.map((row) => row.map((value) => value ?? "")),
  };
}


const model = JSON.parse(await fs.readFile(modelPath, "utf8"));
const table = model.formal_table;
if (table.positions_m.length !== 9) {
  throw new Error("正式结果必须恰有 9 个位置");
}

const sourceHashBefore = await sha256(sourcePath);
if (sourceHashBefore !== model.source_template.sha256) {
  throw new Error("附件 01 的当前哈希与模型运行时记录不一致");
}

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(sourcePath));
const sheet = workbook.worksheets.getItemAt(0);
const before = {
  sheetName: sheet.name,
  values: sheet.getRange("A1:J4").values.map((row) => row.map(normalizeCell)),
  formulas: sheet.getRange("A1:J4").formulas,
};

sheet.getRange("B2:J2").values = [table.depth_m];
sheet.getRange("B3:J3").values = [table.coverage_width_m];
sheet.getRange("B4:J4").values = [["——", ...table.overlap_rate_previous_pct.slice(1)]];
sheet.getRange("B2:J3").format.numberFormat = "0.00";
sheet.getRange("C4:J4").format.numberFormat = "0.00";

workbook.recalculate();

const keyRangeInspection = await workbook.inspect({
  kind: "table",
  range: `${sheet.name}!A1:J4`,
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 12,
  summary: "问题 1 正式结果表",
});
const errorScan = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "最终公式错误扫描",
});

const preview = await workbook.render({
  sheetName: sheet.name,
  range: "A1:J4",
  scale: 2,
  format: "png",
});
await fs.mkdir(path.dirname(previewPath), { recursive: true });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(versionedPath);
await fs.copyFile(versionedPath, submissionPath);

const sourceHashAfter = await sha256(sourcePath);
const versionedHash = await sha256(versionedPath);
const submissionHash = await sha256(submissionPath);
const versionedReadback = await readRange(versionedPath);
const submissionReadback = await readRange(submissionPath);

const expectedValues = [
  ["测线距中心点处的距离/m", ...table.positions_m],
  ["海水深度/m", ...table.depth_m],
  ["覆盖宽度/m", ...table.coverage_width_m],
  ["与前一条测线的重叠率/%", "——", ...table.overlap_rate_previous_pct.slice(1)],
];
const valuesMatch =
  JSON.stringify(versionedReadback.values) === JSON.stringify(expectedValues) &&
  JSON.stringify(submissionReadback.values) === JSON.stringify(expectedValues);
const formulasAbsent = [...versionedReadback.formulas, ...submissionReadback.formulas]
  .flat()
  .every((value) => value === "");
const numericCellsAreNumbers = [
  ...versionedReadback.values[0].slice(1),
  ...versionedReadback.values[1].slice(1),
  ...versionedReadback.values[2].slice(1),
  ...versionedReadback.values[3].slice(2),
].every((value) => typeof value === "number" && Number.isFinite(value));
const centerDepthCorrect = versionedReadback.values[1][5] === 70;
const firstOverlapIsNonNumeric =
  typeof versionedReadback.values[3][1] !== "number" &&
  versionedReadback.values[3][1] === "——";
const hashesIdentical = versionedHash === submissionHash;
const sourceUnchanged = sourceHashBefore === sourceHashAfter;
const formulaErrorPattern = /#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A/;
const formulaErrorCells = [];
for (let row = 0; row < versionedReadback.values.length; row += 1) {
  for (let column = 0; column < versionedReadback.values[row].length; column += 1) {
    const value = versionedReadback.values[row][column];
    const formula = versionedReadback.formulas[row][column];
    if (
      formulaErrorPattern.test(String(value ?? "")) ||
      formulaErrorPattern.test(String(formula ?? ""))
    ) {
      formulaErrorCells.push({ row: row + 1, column: column + 1, value, formula });
    }
  }
}
const formulaErrorCount = formulaErrorCells.length;

const audit = {
  schema_version: "q01-excel-audit-v001",
  generated_at: new Date().toISOString(),
  source: {
    path: "附件/附件01.xlsx",
    sha256_before: sourceHashBefore,
    sha256_after: sourceHashAfter,
    unchanged: sourceUnchanged,
  },
  outputs: {
    versioned: {
      path: "工作记录/结果/Q01/result1-v001.xlsx",
      sha256: versionedHash,
    },
    submission: { path: "result1.xlsx", sha256: submissionHash },
    byte_identical: hashesIdentical,
  },
  template_before: before,
  readback: versionedReadback,
  checks: {
    nine_positions_present: versionedReadback.values[0].length === 10,
    center_depth_correct: centerDepthCorrect,
    first_overlap_non_numeric_dash: firstOverlapIsNonNumeric,
    remaining_eight_overlap_values_present:
      versionedReadback.values[3].slice(2).length === 8,
    numeric_result_cells_are_numbers: numericCellsAreNumbers,
    values_match_formal_table: valuesMatch,
    formulas_absent: formulasAbsent,
    formula_error_count: formulaErrorCount,
    output_files_byte_identical: hashesIdentical,
    source_template_unchanged: sourceUnchanged,
  },
  artifact_tool_inspection: keyRangeInspection,
  formula_error_scan: {
    artifact_tool_result: errorScan,
    direct_readback_error_cells: formulaErrorCells,
    interpretation:
      "artifact-tool 的 inspect 返回记录数含元数据包装；正式错误数按 A1:J4 读回值与公式逐格匹配错误标记确定。",
  },
  preview: "工作记录/诊断结果/Q01/result1-生成后预览-v001.png",
};
audit.all_passed =
  Object.entries(audit.checks).every(([name, value]) =>
    name === "formula_error_count" ? value === 0 : value === true,
  );
await fs.writeFile(auditPath, `${JSON.stringify(audit, null, 2)}\n`, "utf8");
console.log(JSON.stringify(audit, null, 2));
if (!audit.all_passed) {
  throw new Error("Excel 读回核验未全部通过");
}
