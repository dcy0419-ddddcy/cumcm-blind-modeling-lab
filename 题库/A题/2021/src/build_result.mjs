import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = process.cwd();
const templatePath = path.join(root, "附件", "附件04.xlsx");
const dataPath = path.join(root, "outputs", "result_data.json");
const outputPath = path.join(root, "result.xlsx");
const previewDir = path.join(root, ".artifact_build", "previews");
const expectedSheets = [
  "理想抛物面顶点坐标",
  "调整后主索节点编号及坐标",
  "促动器顶端伸缩量",
];

const data = JSON.parse(await fs.readFile(dataPath, "utf8"));
if (data.nodes.length !== data.actuators.length || data.nodes.length === 0) {
  throw new Error("Node and actuator row counts must be equal and nonzero");
}
const nodeIds = data.nodes.map((row) => row[0]);
const actuatorIds = data.actuators.map((row) => row[0]);
if (new Set(nodeIds).size !== nodeIds.length ||
    JSON.stringify(nodeIds) !== JSON.stringify(actuatorIds)) {
  throw new Error("Node/actuator identifiers are not unique and aligned");
}
const input = await FileBlob.load(templatePath);
const workbook = await SpreadsheetFile.importXlsx(input);

const sheetInfo = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 3000,
});
console.log("TEMPLATE_SHEETS");
console.log(sheetInfo.ndjson);

for (const name of expectedSheets) {
  if (!workbook.worksheets.getItem(name)) {
    throw new Error(`Missing template sheet: ${name}`);
  }
}

const vertexSheet = workbook.worksheets.getItem(expectedSheets[0]);
const nodeSheet = workbook.worksheets.getItem(expectedSheets[1]);
const actuatorSheet = workbook.worksheets.getItem(expectedSheets[2]);

vertexSheet.getRange("A2:C2").values = [data.vertex];
vertexSheet.getRange("A2:C2").format.numberFormat = "0.000000";
vertexSheet.getRange("A1:C2").format.columnWidth = 18;
vertexSheet.freezePanes.freezeRows(1);

const nodeLast = data.nodes.length + 1;
nodeSheet.getRange(`A2:D${nodeLast}`).values = data.nodes;
nodeSheet.getRange(`B2:D${nodeLast}`).format.numberFormat = "0.000000";
nodeSheet.getRange(`A2:A${nodeLast}`).format.horizontalAlignment = "left";
nodeSheet.getRange(`A1:A${nodeLast}`).format.columnWidth = 22;
nodeSheet.getRange(`B1:D${nodeLast}`).format.columnWidth = 18;
nodeSheet.freezePanes.freezeRows(1);

const actuatorLast = data.actuators.length + 1;
actuatorSheet.getRange(`A2:B${actuatorLast}`).values = data.actuators;
actuatorSheet.getRange(`B2:B${actuatorLast}`).format.numberFormat = "0.000000";
actuatorSheet.getRange(`A2:A${actuatorLast}`).format.horizontalAlignment = "left";
actuatorSheet.getRange(`A1:A${actuatorLast}`).format.columnWidth = 22;
actuatorSheet.getRange(`B1:B${actuatorLast}`).format.columnWidth = 18;
actuatorSheet.freezePanes.freezeRows(1);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);

const reopened = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
function assertMatrixMatches(actual, expected, label) {
  if (!Array.isArray(actual) || actual.length !== expected.length) {
    throw new Error(`${label}: row count mismatch`);
  }
  for (let row = 0; row < expected.length; row += 1) {
    if (!Array.isArray(actual[row]) || actual[row].length !== expected[row].length) {
      throw new Error(`${label}: column count mismatch at row ${row + 1}`);
    }
    for (let col = 0; col < expected[row].length; col += 1) {
      const left = actual[row][col];
      const right = expected[row][col];
      const equal = (typeof left === "number" && typeof right === "number")
        ? Math.abs(left - right) <= 1e-12
        : left === right;
      if (!equal) {
        throw new Error(`${label}: value mismatch at row ${row + 1}, column ${col + 1}`);
      }
    }
  }
}

assertMatrixMatches(
  await reopened.worksheets.getItem(expectedSheets[0]).getRange("A2:C2").values,
  [data.vertex], "vertex");
assertMatrixMatches(
  await reopened.worksheets.getItem(expectedSheets[1])
    .getRange(`A2:D${nodeLast}`).values,
  data.nodes, "nodes");
assertMatrixMatches(
  await reopened.worksheets.getItem(expectedSheets[2])
    .getRange(`A2:B${actuatorLast}`).values,
  data.actuators, "actuators");

await fs.mkdir(previewDir, { recursive: true });
for (const [name, range, fileName] of [
  [expectedSheets[0], "A1:C2", "sheet1.png"],
  [expectedSheets[1], "A1:D18", "sheet2_top.png"],
  [expectedSheets[2], "A1:B18", "sheet3_top.png"],
]) {
  const preview = await reopened.render({ sheetName: name, range, scale: 2, format: "png" });
  await fs.writeFile(path.join(previewDir, fileName),
                     new Uint8Array(await preview.arrayBuffer()));
}

for (const [name, range] of [
  [expectedSheets[0], "A1:C2"],
  [expectedSheets[1], "A1:D6"],
  [expectedSheets[1], `A${nodeLast - 3}:D${nodeLast}`],
  [expectedSheets[2], "A1:B6"],
  [expectedSheets[2], `A${actuatorLast - 3}:B${actuatorLast}`],
]) {
  const check = await reopened.inspect({
    kind: "table",
    range: `${name}!${range}`,
    include: "values,formulas",
    tableMaxRows: 8,
    tableMaxCols: 5,
    maxChars: 3500,
  });
  console.log(`CHECK ${name}!${range}`);
  console.log(check.ndjson);
}
const errors = await reopened.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
  maxChars: 3000,
});
console.log("FORMULA_ERROR_SCAN");
console.log(errors.ndjson);
console.log(JSON.stringify({ outputPath, nodeRows: data.nodes.length,
                             actuatorRows: data.actuators.length,
                             fullValueMatch: true }));
