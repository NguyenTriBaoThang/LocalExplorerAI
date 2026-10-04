import fs from 'node:fs/promises';
import { FileBlob, SpreadsheetFile } from 'file:///C:/Users/BaoThang-PC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const source = 'G:/GITHUB/LoaclExplorerAI/data/raw/Sai_Gon_Places.xlsx';
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const summary = await workbook.inspect({
  kind: 'workbook,sheet,table',
  maxChars: 12000,
  tableMaxRows: 4,
  tableMaxCols: 40,
  tableMaxCellChars: 100,
});
console.log('SUMMARY');
console.log(summary.ndjson ?? JSON.stringify(summary));
console.log('SHEETS');
const sheets = await workbook.inspect({ kind: 'sheet', include: 'id,name' });
console.log(sheets.ndjson ?? JSON.stringify(sheets));
const sheet = workbook.worksheets.getItem('Sai_Gon');
const rows = sheet.getUsedRange().values;
const headers = rows[0];
const records = rows.slice(1).map((cells) => Object.fromEntries(headers.map((header, index) => [header, cells[index] ?? null])));
console.log('COLUMNS');
console.log(JSON.stringify(headers));
console.log('MISSING_COUNTS');
console.log(JSON.stringify(Object.fromEntries(headers.map((header, index) => [header, records.filter((row) => row[header] === null || row[header] === '').length]))));
console.log('DISTRIBUTION');
console.log(JSON.stringify({
  records: records.length,
  verified: records.filter((row) => row.verified === true).length,
  verifiedFalse: records.filter((row) => row.verified === false).length,
  distinctLatLonPairs: new Set(records.map((row) => `${row.lat},${row.lon}`)).size,
  latLonCounts: Object.fromEntries([...new Set(records.map((row) => `${row.lat},${row.lon}`))].map((key) => [key, records.filter((row) => `${row.lat},${row.lon}` === key).length])),
  sources: Object.fromEntries([...new Set(records.map((row) => row.source))].map((key) => [key, records.filter((row) => row.source === key).length])),
  kinds: Object.fromEntries([...new Set(records.map((row) => row.kind))].map((key) => [key, records.filter((row) => row.kind === key).length])),
  duplicateExtIdCount: records.length - new Set(records.map((row) => row.ext_id)).size,
}));
console.log('PLACES');
for (const row of records) console.log(`${row.ext_id}\t${row.name}\t${row.kind}\t${row.verified}\t${row.source}`);
