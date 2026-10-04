import fs from 'node:fs/promises';
import { FileBlob, SpreadsheetFile } from 'file:///C:/Users/BaoThang-PC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const inputPath = 'G:/GITHUB/LoaclExplorerAI/data/raw/Sai_Gon_Places.xlsx';
const outputDir = 'G:/GITHUB/LoaclExplorerAI/outputs/sai-gon-places-20261004';
const outputPath = `${outputDir}/Sai_Gon_Places_Enriched_2026-10-04.xlsx`;
const checkedAt = '2026-10-04';
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sourceSheet = workbook.worksheets.getItem('Sai_Gon');
const rawMatrix = sourceSheet.getUsedRange().values;
const rawHeaders = rawMatrix[0];
const rawObjects = rawMatrix.slice(1).map((row) => Object.fromEntries(rawHeaders.map((key, index) => [key, row[index] ?? null])));
const byId = new Map(rawObjects.map((row) => [row.ext_id, row]));

const citedSources = {
  dinhHoursAndPrices: 'https://dinhdoclap.gov.vn/en/visiting-hours/',
  dinhAddress: 'https://dinhdoclap.gov.vn/lien-he/',
  warMuseum: 'https://ticket.baotangchungtichchientranh.vn/terms-and-conditions.html',
  zooPrices: 'https://www.saigonzoo.vn/ve-tham-quan',
  zooAddressHours: 'https://saigonzoo.vn/p/cau-hoi-thuong-gap-hp16.html',
  fineArtsPrice: 'https://baotangmythuattphcm.com.vn/tham-quan/so-do-tham-quan',
  fineArtsAddress: 'https://baotang.dsvh.gov.vn/vi-VN/Detail/Index/122',
  historyMuseum: 'https://www.baotanglichsutphcm.com.vn/tham-quan/chinh-sach',
  cityTourismGuide: 'https://visithcmc.net/en/page/ke-hoach-chuyen-di',
};

const researched = new Map([
  ['sai-gon-dinh-oc-lap', {
    address: '135 Nam Kỳ Khởi Nghĩa, phường Bến Thành, TP. Hồ Chí Minh',
    price_vnd: 80000,
    price_scope: 'Vé tổng hợp người lớn (Dinh + Nhà trưng bày); loại vé khác có mức riêng.',
    open_hours: JSON.stringify({ days: 'Mon-Sun', open: '07:00', close: '18:00', note: 'Cổng 106 Nguyễn Du bán vé đến 16:00.' }),
    description: 'Di tích lịch sử quốc gia; tham quan Dinh và khu trưng bày theo loại vé đã chọn.',
    contact: 'https://dinhdoclap.gov.vn | 091.6624.419; 028.3822.3652',
    source_url: `${citedSources.dinhHoursAndPrices}\n${citedSources.dinhAddress}`,
    field_evidence: 'Địa chỉ, giờ tham quan và vé tổng hợp người lớn có nguồn chính thức. Tọa độ, sức chứa, thời lượng tham quan, giờ từng dịch vụ và ảnh chưa được đối chiếu.',
  }],
  ['sai-gon-bao-tang-chung-tich-chien-tranh', {
    address: '28 Võ Văn Tần, phường Xuân Hòa, TP. Hồ Chí Minh',
    price_vnd: 40000,
    price_scope: 'Vé người lớn; trẻ em 6–dưới 16 tuổi và học sinh/sinh viên có thẻ: 20.000 VND; dưới 6 tuổi miễn phí.',
    open_hours: JSON.stringify({ days: 'Mon-Sun', open: '07:30', close: '17:30', ticket_desk_closes: '17:00' }),
    description: 'Bảo tàng có các không gian trưng bày trong nhà và khu trưng bày hiện vật ngoài sân.',
    contact: 'https://ticket.baotangchungtichchientranh.vn | 028 3930 6325 (line 18)',
    source_url: citedSources.warMuseum,
    field_evidence: 'Điều khoản/vé trực tuyến của bảo tàng ghi địa chỉ, giờ và bảng giá; tọa độ, sức chứa, thời lượng, ảnh chưa xác minh.',
  }],
  ['sai-gon-thao-cam-vien-sai-gon', {
    address: '02 Nguyễn Bỉnh Khiêm, phường Sài Gòn, TP. Hồ Chí Minh',
    price_vnd: 60000,
    price_scope: 'Vé người lớn áp dụng chiều cao từ 1,3 m; trẻ em 1,0–dưới 1,3 m: 40.000 VND; dưới 1 m đi cùng phụ huynh miễn phí.',
    open_hours: JSON.stringify({ days: 'Mon-Sun', open: '07:00', close: '18:30' }),
    outdoor: true,
    description: 'Thảo Cầm Viên và vườn thực vật; có hoạt động tham quan, giáo dục và dịch vụ trong khuôn viên.',
    contact: 'https://www.saigonzoo.vn | 028 3829 1425',
    source_url: `${citedSources.zooPrices}\n${citedSources.zooAddressHours}`,
    field_evidence: 'Trang của đơn vị vận hành ghi địa chỉ, giờ và giá theo chiều cao. Tọa độ, công suất, thời lượng, ảnh chưa xác minh.',
  }],
  ['sai-gon-bao-tang-my-thuat-thanh-pho-ho-chi-minh', {
    address: '97A Phó Đức Chính, phường Nguyễn Thái Bình, TP. Hồ Chí Minh',
    price_vnd: 30000,
    price_scope: 'Phí tham quan/lượt; trang bảo tàng nêu miễn phí dưới 6 tuổi và giảm phí cho một số nhóm.',
    description: 'Bảo tàng Mỹ thuật Thành phố Hồ Chí Minh; địa chỉ và phí tham quan lấy từ nguồn bảo tàng/di sản.',
    contact: 'https://baotangmythuattphcm.com.vn | 028 3821 6331',
    source_url: `${citedSources.fineArtsPrice}\n${citedSources.fineArtsAddress}`,
    field_evidence: 'Trang bảo tàng công bố mức phí; cổng di sản văn hóa ghi địa chỉ. Giờ mở cửa và tọa độ chưa được xác minh trong nguồn truy cập được.',
  }],
  ['sai-gon-bao-tang-lich-su-thanh-pho-ho-chi-minh', {
    address: '02 Nguyễn Bỉnh Khiêm, phường Bến Nghé, Quận 1, TP. Hồ Chí Minh',
    price_vnd: 30000,
    price_scope: 'Phí tham quan/lượt; một số nhóm được miễn hoặc giảm 50% theo chính sách của bảo tàng.',
    open_hours: JSON.stringify({ days: 'Tue-Sun', morning: '08:00-11:30', afternoon: '13:00-17:00', closed: 'Mon' }),
    description: 'Bảo tàng Lịch sử Thành phố Hồ Chí Minh; thông tin giá, giờ và địa chỉ lấy từ website bảo tàng.',
    contact: 'https://www.baotanglichsutphcm.com.vn | 028 3825 8783',
    source_url: citedSources.historyMuseum,
    field_evidence: 'Trang chính sách của bảo tàng ghi phí, giờ, địa chỉ và chính sách ưu đãi; tọa độ, sức chứa, thời lượng, ảnh chưa xác minh.',
  }],
  ['sai-gon-cho-ben-thanh', {
    address: 'Cửa chính tại Quảng trường Quách Thị Trang; các cổng trên Lê Thánh Tôn, Phan Bội Châu và Phan Chu Trinh, TP. Hồ Chí Minh',
    open_hours: JSON.stringify({ days: 'Mon-Sun', market: '07:00-19:00', night_market: '19:00-24:00', note: 'Theo hướng dẫn du lịch TP.HCM; nên xác nhận lại với chợ trước khi đến.' }),
    price_scope: 'Không có giá vé cố định được xác minh; chi tiêu mua sắm/ăn uống thay đổi theo quầy và món.',
    description: 'Chợ truyền thống và điểm mua sắm/ẩm thực; trang du lịch TP.HCM nêu vị trí các cổng và khung giờ.',
    source_url: citedSources.cityTourismGuide,
    field_evidence: 'Trang du lịch chính thức của TP.HCM ghi vị trí cổng và giờ khung; đây không phải xác nhận trực tiếp của ban quản lý chợ.',
  }],
  ['sai-gon-cong-vien-tao-an', {
    address: '55C Nguyễn Thị Minh Khai, TP. Hồ Chí Minh',
    open_hours: JSON.stringify({ days: 'Mon-Sun', open: '00:00', close: '24:00' }),
    outdoor: true,
    description: 'Công viên Tao Đàn; trang du lịch TP.HCM ghi địa chỉ và hoạt động 24 giờ.',
    source_url: citedSources.cityTourismGuide,
    field_evidence: 'Địa chỉ và giờ lấy từ hướng dẫn du lịch TP.HCM; giờ/điều kiện tại từng cổng và sự kiện đặc biệt cần xác nhận.',
  }],
]);

const enrichedHeaders = [
  'ext_id', 'name', 'kind', 'address', 'lat', 'lon', 'price_vnd', 'price_scope', 'open_hours',
  'outdoor', 'tags', 'description', 'photo_url', 'contact_or_website', 'source_url',
  'source_checked_at', 'data_status', 'verified', 'field_evidence', 'duration_min', 'capacity',
];
const enrichedRows = rawObjects.map((raw) => {
  const sourced = researched.get(raw.ext_id);
  const row = {
    ext_id: raw.ext_id,
    name: raw.name,
    kind: raw.kind,
    address: sourced?.address ?? null,
    lat: null,
    lon: null,
    price_vnd: sourced?.price_vnd ?? null,
    price_scope: sourced?.price_scope ?? null,
    open_hours: sourced?.open_hours ?? null,
    outdoor: sourced?.outdoor ?? null,
    tags: null,
    description: sourced?.description ?? null,
    photo_url: null,
    contact_or_website: sourced?.contact ?? null,
    source_url: sourced?.source_url ?? null,
    source_checked_at: sourced ? checkedAt : null,
    data_status: sourced ? 'partial_source' : 'needs_source_verification',
    verified: false,
    field_evidence: sourced?.field_evidence ?? 'Chưa có URL nguồn theo từng địa điểm trong workbook. Giá/giờ/tọa độ/loại hình của bản gốc chưa được coi là dữ liệu vận hành.',
    duration_min: null,
    capacity: null,
  };
  return enrichedHeaders.map((key) => row[key] ?? null);
});

const coordCounts = new Map();
for (const row of rawObjects) {
  const key = `${row.lat},${row.lon}`;
  coordCounts.set(key, (coordCounts.get(key) ?? 0) + 1);
}
const coordCountsJson = JSON.stringify(Object.fromEntries(coordCounts));
const auditHeaders = [
  'ext_id', 'name', 'kind_from_source', 'raw_lat', 'raw_lon', 'coordinate_cluster_count',
  'raw_price_vnd', 'raw_open_hours', 'raw_outdoor', 'raw_tags', 'raw_photo_url',
  'raw_verified', 'raw_source_label', 'quality_flags', 'next_action',
];
const auditRows = rawObjects.map((row) => {
  const coordinateClusterCount = coordCounts.get(`${row.lat},${row.lon}`) ?? 0;
  const flags = [
    'Không có cột địa chỉ',
    'open_hours là {} (không có giờ thực)',
    'photo_url trống',
    `Tọa độ thuộc cụm lặp ${coordinateClusterCount} bản ghi`,
    row.source === 'Vietnam Tourism / danh sách ứng viên' ? 'Nguồn chỉ là nhãn danh sách, không có URL theo POI' : 'Nhãn nguồn không kèm URL/bằng chứng theo trường',
    row.verified === true ? 'verified=true không có URL/evidence trong workbook' : 'Chưa có bằng chứng trường dữ liệu trong workbook',
    'Giá, phân loại, tag, mô tả chưa có nguồn theo từng dòng',
  ].join('; ');
  const next = researched.has(row.ext_id)
    ? 'Bổ sung tọa độ từ nguồn bản đồ có giấy phép; xác minh ảnh/thời lượng/đặc tính còn thiếu.'
    : 'Tìm trang đơn vị vận hành/nguồn bản đồ phù hợp; xác minh địa chỉ, tọa độ, giá, giờ, loại, nguồn và ngày hết hạn.';
  return [row.ext_id, row.name, row.kind, row.lat, row.lon, coordinateClusterCount, row.price_vnd, row.open_hours, row.outdoor, row.tags, row.photo_url, row.verified, row.source, flags, next];
});

const evidenceRows = [
  ['Dinh Độc Lập', citedSources.dinhHoursAndPrices, 'Đơn vị quản lý di tích (official)', 'Giờ tham quan và vé người lớn tổng hợp 80.000 VND; giá áp dụng từ 01/05/2026.', checkedAt],
  ['Dinh Độc Lập', citedSources.dinhAddress, 'Đơn vị quản lý di tích (official)', 'Địa chỉ 135 Nam Kỳ Khởi Nghĩa và 106 Nguyễn Du; giờ hoạt động.', checkedAt],
  ['Bảo tàng Chứng tích Chiến tranh', citedSources.warMuseum, 'Bảo tàng / hệ thống vé chính thức', 'Địa chỉ, giờ mở cửa, giờ đóng quầy vé và giá người lớn 40.000 VND; trang ghi cập nhật 01/01/2026.', checkedAt],
  ['Thảo Cầm Viên Sài Gòn', citedSources.zooPrices, 'Đơn vị vận hành (official)', 'Giá theo chiều cao: người lớn 60.000; trẻ em 40.000 VND.', checkedAt],
  ['Thảo Cầm Viên Sài Gòn', citedSources.zooAddressHours, 'Đơn vị vận hành (official)', 'Địa chỉ 02 Nguyễn Bỉnh Khiêm, giờ 07:00–18:30 mỗi ngày.', checkedAt],
  ['Bảo tàng Mỹ thuật TP.HCM', citedSources.fineArtsPrice, 'Website bảo tàng (official)', 'Phí tham quan 30.000 VND/lượt; giờ không điền vì chưa xác nhận được trong trang này.', checkedAt],
  ['Bảo tàng Mỹ thuật TP.HCM', citedSources.fineArtsAddress, 'Cổng thông tin di sản văn hóa', 'Địa chỉ 97A Phó Đức Chính; liên hệ bảo tàng.', checkedAt],
  ['Bảo tàng Lịch sử TP.HCM', citedSources.historyMuseum, 'Website bảo tàng (official)', 'Địa chỉ, lịch mở cửa và phí tham quan 30.000 VND/lượt.', checkedAt],
  ['Chợ Bến Thành', citedSources.cityTourismGuide, 'Trang du lịch chính thức TP.HCM', 'Vị trí các cổng và khung giờ chợ; không coi là bảng giá của từng sạp.', checkedAt],
  ['Công viên Tao Đàn', citedSources.cityTourismGuide, 'Trang du lịch chính thức TP.HCM', 'Địa chỉ 55C Nguyễn Thị Minh Khai và khung giờ công viên.', checkedAt],
];

await fs.mkdir(outputDir, { recursive: true });
const enrichedSheet = workbook.worksheets.add('Sai_Gon_Enriched');
enrichedSheet.showGridLines = false;
enrichedSheet.getRangeByIndexes(0, 0, 1, enrichedHeaders.length).values = [enrichedHeaders];
enrichedSheet.getRangeByIndexes(1, 0, enrichedRows.length, enrichedHeaders.length).values = enrichedRows;
enrichedSheet.freezePanes.freezeRows(1);
enrichedSheet.getRange(`A1:U1`).format.fill = '#0F3D56';
enrichedSheet.getRange('A1:U1').format.font = { bold: true, color: '#FFFFFF' };
enrichedSheet.getRange(`A1:U${enrichedRows.length + 1}`).format.wrapText = true;
enrichedSheet.getRange('A1:U1').format.rowHeight = 30;
enrichedSheet.getRange('A:A').format.columnWidth = 34;
enrichedSheet.getRange('B:C').format.columnWidth = 30;
enrichedSheet.getRange('D:D').format.columnWidth = 45;
enrichedSheet.getRange('E:F').format.columnWidth = 13;
enrichedSheet.getRange('G:G').format.columnWidth = 16;
enrichedSheet.getRange('H:H').format.columnWidth = 44;
enrichedSheet.getRange('I:I').format.columnWidth = 32;
enrichedSheet.getRange('J:J').format.columnWidth = 12;
enrichedSheet.getRange('K:K').format.columnWidth = 30;
enrichedSheet.getRange('L:L').format.columnWidth = 50;
enrichedSheet.getRange('M:M').format.columnWidth = 28;
enrichedSheet.getRange('N:N').format.columnWidth = 42;
enrichedSheet.getRange('O:O').format.columnWidth = 56;
enrichedSheet.getRange('P:P').format.columnWidth = 17;
enrichedSheet.getRange('Q:R').format.columnWidth = 27;
enrichedSheet.getRange('S:S').format.columnWidth = 66;
enrichedSheet.getRange('T:U').format.columnWidth = 15;

const auditSheet = workbook.worksheets.add('QA_177');
auditSheet.showGridLines = false;
auditSheet.getRangeByIndexes(0, 0, 1, auditHeaders.length).values = [auditHeaders];
auditSheet.getRangeByIndexes(1, 0, auditRows.length, auditHeaders.length).values = auditRows;
auditSheet.freezePanes.freezeRows(1);
auditSheet.getRange('A1:O1').format.fill = '#5B3A29';
auditSheet.getRange('A1:O1').format.font = { bold: true, color: '#FFFFFF' };
auditSheet.getRange(`A1:O${auditRows.length + 1}`).format.wrapText = true;
auditSheet.getRange('A:A').format.columnWidth = 34;
auditSheet.getRange('B:C').format.columnWidth = 30;
auditSheet.getRange('D:F').format.columnWidth = 18;
auditSheet.getRange('G:G').format.columnWidth = 16;
auditSheet.getRange('H:H').format.columnWidth = 22;
auditSheet.getRange('I:M').format.columnWidth = 22;
auditSheet.getRange('N:O').format.columnWidth = 70;

const evidenceSheet = workbook.worksheets.add('Evidence');
evidenceSheet.showGridLines = false;
const evidenceHeaders = ['place_name', 'source_url', 'source_authority', 'fields_supported / note', 'checked_at'];
evidenceSheet.getRange('A1:E1').values = [evidenceHeaders];
evidenceSheet.getRangeByIndexes(1, 0, evidenceRows.length, evidenceHeaders.length).values = evidenceRows;
evidenceSheet.freezePanes.freezeRows(1);
evidenceSheet.getRange('A1:E1').format.fill = '#0F3D56';
evidenceSheet.getRange('A1:E1').format.font = { bold: true, color: '#FFFFFF' };
evidenceSheet.getRange(`A1:E${evidenceRows.length + 1}`).format.wrapText = true;
evidenceSheet.getRange('A:A').format.columnWidth = 34;
evidenceSheet.getRange('B:B').format.columnWidth = 76;
evidenceSheet.getRange('C:C').format.columnWidth = 36;
evidenceSheet.getRange('D:D').format.columnWidth = 76;
evidenceSheet.getRange('E:E').format.columnWidth = 18;

const readmeSheet = workbook.worksheets.add('README_Enrichment');
readmeSheet.showGridLines = false;
const enrichedCount = researched.size;
const uniqueCoordinatePairs = coordCounts.size;
const summaryRows = [
  ['Sai Gon Places — kiểm tra và bổ sung có nguồn', '2026-10-04'],
  ['Bản gốc', 'Giữ nguyên sheet Sai_Gon và các sheet nguồn trong workbook; không sửa file data/raw/Sai_Gon_Places.xlsx.'],
  ['Số bản ghi', rawObjects.length],
  ['Số bản ghi có một phần dữ liệu từ nguồn công khai', `${enrichedCount}; xem Sai_Gon_Enriched và Evidence.`],
  ['Số bản ghi chưa có nguồn theo từng địa điểm', rawObjects.length - enrichedCount],
  ['Cờ verified ở sheet kết quả', 'FALSE cho toàn bộ 177 dòng: không dòng nào có đủ tọa độ chính xác + bằng chứng phủ mọi trường để coi là POI vận hành.'],
  ['Lỗi tọa độ nguồn', `${uniqueCoordinatePairs} cặp lat/lon lặp cho 177 dòng (${coordCountsJson}); không sao chép sang sheet kết quả.`],
  ['Giờ / ảnh nguồn', '177/177 open_hours là {}; 177/177 photo_url trống.'],
  ['Nguồn theo từng dòng', '157 dòng chỉ gắn nhãn “Vietnam Tourism / danh sách ứng viên”; 20 dòng chỉ gắn “business search hiện tại”, không có URL chứng cứ theo trường.'],
  ['Quy ước giá', 'price_vnd là giá cơ bản người lớn/đối tượng ghi trong price_scope; ô trống = chưa tìm thấy giá có thể xác nhận, KHÔNG có nghĩa là miễn phí.'],
  ['Hạn chế quan trọng', 'Không dùng các dòng này để đặt chỗ, tối ưu tuyến hoặc xác nhận mở cửa. Những dòng partial_source vẫn thiếu lat/lon, ảnh, giờ/giá/đặc tính có thể áp dụng theo ngày.'],
  ['Tọa độ', 'Cần geocoding có giấy phép hoặc đo/đối chiếu nguồn bản đồ được nhóm chọn. Không dùng public Nominatim để chạy hàng loạt hoặc lấy cả tập POI.'],
  ['Duration / capacity / slots', 'Để trống: đây là thông tin cấp trải nghiệm/cơ sở/ca và không thể suy ra từ tên POI. Cần chủ cơ sở xác nhận.'],
  ['Sheet Sai_Gon_Enriched', 'Bản chuẩn hóa an toàn: chỉ điền các trường có nguồn công khai đã liệt kê; còn lại để trống thay vì giữ giá, giờ và tọa độ không có bằng chứng.'],
  ['Sheet QA_177', 'Đối chiếu giá trị gốc và cờ chất lượng theo từng record để nhóm tiếp tục xác minh.'],
  ['Sheet Evidence', 'URL trực tiếp và phạm vi trường mà mỗi nguồn hỗ trợ; ngày kiểm tra 2026-10-04.'],
];
readmeSheet.getRangeByIndexes(0, 0, summaryRows.length, 2).values = summaryRows;
readmeSheet.getRange('A1:B1').format.fill = '#0F3D56';
readmeSheet.getRange('A1:B1').format.font = { bold: true, color: '#FFFFFF', size: 14 };
readmeSheet.getRange(`A1:B${summaryRows.length}`).format.wrapText = true;
readmeSheet.getRange('A:A').format.columnWidth = 38;
readmeSheet.getRange('B:B').format.columnWidth = 120;
readmeSheet.freezePanes.freezeRows(1);

workbook.recalculate();
for (const spec of [
  { kind: 'region', sheetId: 'Sai_Gon_Enriched', range: 'A1:U10', maxChars: 8000 },
  { kind: 'region', sheetId: 'README_Enrichment', range: 'A1:B16', maxChars: 8000 },
]) {
  const inspection = await workbook.inspect(spec);
  console.log(inspection.ndjson ?? JSON.stringify(inspection));
}
const preview = await workbook.render({ sheetName: 'README_Enrichment', autoCrop: 'all', scale: 1, format: 'png' });
await fs.writeFile('G:/GITHUB/LoaclExplorerAI/.codex/tmp/sai-gon-places-20261004/README_Enrichment.png', new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`OUTPUT_PATH=${outputPath}`);
console.log(`ROWS=${rawObjects.length}; PARTIAL=${enrichedCount}; UNSOURCED=${rawObjects.length - enrichedCount}; COORD_CLUSTERS=${coordCounts.size}`);
