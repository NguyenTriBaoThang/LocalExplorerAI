import { FileBlob, SpreadsheetFile } from 'file:///C:/Users/BaoThang-PC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
for (const path of [
  'G:/GITHUB/LoaclExplorerAI/data/raw/Sai_Gon_Places.xlsx',
  'G:/GITHUB/LoaclExplorerAI/outputs/sai-gon-places-20261004/Sai_Gon_Places_Enriched_2026-10-04.xlsx',
]) {
  const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(path));
  const s = wb.worksheets.getItem(path.includes('outputs') ? 'Sai_Gon_Enriched' : 'Sai_Gon');
  const v = s.getUsedRange().values;
  const h = v[0];
  const iId = h.indexOf('ext_id');
  const iLat = h.indexOf('lat');
  const iLon = h.indexOf('lon');
  const target = v.find((row) => String(row[iId]) === 'sai-gon-dinh-oc-lap');
  const ids = v.slice(1).map((row) => String(row[iId]));
  const coords = new Map();
  for (const row of v.slice(1)) {
    const key = `${JSON.stringify(row[iLat])},${JSON.stringify(row[iLon])}`;
    coords.set(key, (coords.get(key) ?? 0) + 1);
  }
  const indices = Object.fromEntries(h.map((key, index) => [key, index]));
  const rawRows = v.slice(1);
  const blanks = Object.fromEntries(h.map((key, index) => [key, rawRows.filter((row) => row[index] === null || row[index] === '').length]));
  const coordDuplicates = [...coords.entries()].filter(([, count]) => count > 1);
  const sourceDist = Object.fromEntries([...new Set(rawRows.map((row) => row[indices.source]))].map((key) => [key, rawRows.filter((row) => row[indices.source] === key).length]));
  const coordBounds = rawRows.reduce((acc, row) => {
    const lat = row[iLat]; const lon = row[iLon];
    if (typeof lat === 'number' && typeof lon === 'number') {
      acc.minLat = Math.min(acc.minLat, lat); acc.maxLat = Math.max(acc.maxLat, lat);
      acc.minLon = Math.min(acc.minLon, lon); acc.maxLon = Math.max(acc.maxLon, lon);
      if (lat < 10.2 || lat > 11.4 || lon < 106.1 || lon > 107.2) acc.outsideBroadHcmcBox++;
    }
    return acc;
  }, { minLat: Infinity, maxLat: -Infinity, minLon: Infinity, maxLon: -Infinity, outsideBroadHcmcBox: 0 });
  const columnStats = Object.fromEntries(h.map((key, index) => [key, {
    unique: new Set(rawRows.map((row) => JSON.stringify(row[index]))).size,
    nullOrEmpty: rawRows.filter((row) => row[index] === null || row[index] === '').length,
    samples: [...new Set(rawRows.map((row) => row[index]))].slice(0, 4),
  }]));
  console.log(JSON.stringify({ path, headers: h, count: v.length - 1, target, distinctIds: new Set(ids).size, distinctCoords: coords.size, coordDuplicates, coordBounds, blanks, columnStats, sourceDist, verifiedTrue: rawRows.filter((row) => row[indices.verified] === true).length, firstRows: rawRows.slice(0, 5), firstCoords: [...coords.entries()].slice(0, 6) }));
}
