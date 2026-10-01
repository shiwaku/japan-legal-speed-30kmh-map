// npa-traffic-accident-converter/viewer/src/popup.ts から移植(変更なし)
function esc(v: unknown): string {
  return String(v ?? "-")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function buildPopupHtml(
  props: Record<string, unknown>,
  lng: number,
  lat: number
): string {
  const jikonaiyo = String(props["事故内容"] ?? "");
  const isFatal = jikonaiyo === "死亡事故";
  const headerColor = isFatal ? "#e8003a" : "#2563eb";
  const hasseinichiji = `${props["発生日時_年"]}年${props["発生日時_月"]}月${props["発生日時_日"]}日（${props["曜日(発生年月日)"] ?? "-"}） ${props["発生日時_時"]}時${props["発生日時_分"]}分`;

  const infoRows: [string, unknown][] = [
    ["都道府県", props["都道府県名"]],
    ["警察署等", props["警察署等名"]],
    ["路線名", props["路線名"]],
    ["昼夜", props["昼夜"]],
    ["死者数", props["死者数"]],
    ["負傷者数", props["負傷者数"]],
    ["天候", props["天候"]],
    ["地形", props["地形"]],
    ["路面状態", props["路面状態"]],
    ["道路形状", props["道路形状"]],
    ["信号機", props["信号機"]],
    ["車道幅員", props["車道幅員"]],
    ["道路線形", props["道路線形"]],
    ["衝突地点", props["衝突地点"]],
    ["ゾーン規制", props["ゾーン規制"]],
    ["中央分離帯施設等", props["中央分離帯施設等"]],
    ["歩車道区分", props["歩車道区分"]],
    ["事故類型", props["事故類型"]],
  ];

  const infoGrid = infoRows
    .map(
      ([label, val]) =>
        `<span class="popup-grid-label">${esc(label)}</span><span class="popup-grid-value">${esc(val)}</span>`
    )
    .join("");

  const partyRows: [string, unknown, unknown][] = [
    ["当事者種別", props["当事者種別（当事者A）"], props["当事者種別（当事者B）"]],
    ["年齢層", props["年齢（当事者A）"], props["年齢（当事者B）"]],
    ["人身損傷程度", props["人身損傷程度（当事者A）"], props["人身損傷程度（当事者B）"]],
    ["車両の損壊程度", props["車両の損壊程度（当事者A）"], props["車両の損壊程度（当事者B）"]],
    ["車両の衝突部位", props["車両の衝突部位（当事者A）"], props["車両の衝突部位（当事者B）"]],
    ["用途別", props["用途別（当事者A）"], props["用途別（当事者B）"]],
    ["車両形状", props["車両形状（当事者A）"], props["車両形状（当事者B）"]],
    ["速度規制", props["速度規制（指定のみ）（当事者A）"], props["速度規制（指定のみ）（当事者B）"]],
    ["一時停止_標識", props["一時停止規制_標識（当事者A）"], props["一時停止規制_標識（当事者B）"]],
    ["一時停止_表示", props["一時停止規制_表示（当事者A）"], props["一時停止規制_表示（当事者B）"]],
    ["エアバッグ", props["エアバッグの装備（当事者A）"], props["エアバッグの装備（当事者B）"]],
    ["サイドエアバッグ", props["サイドエアバッグの装備（当事者A）"], props["サイドエアバッグの装備（当事者B）"]],
  ];

  const tableRows = partyRows
    .map(
      ([label, a, b]) =>
        `<tr><td>${esc(label)}</td><td>${esc(a)}</td><td>${esc(b)}</td></tr>`
    )
    .join("");

  return `
    <div class="popup-header" style="background: ${headerColor}">
      ${esc(jikonaiyo)}
      <small>${esc(hasseinichiji)}</small>
    </div>
    <div class="popup-body">
      <div class="popup-section-title">事故情報</div>
      <div class="popup-grid">${infoGrid}</div>
      <div class="popup-section-title">当事者情報</div>
      <table class="popup-table">
        <thead><tr><th>項目</th><th>当事者A</th><th>当事者B</th></tr></thead>
        <tbody>${tableRows}</tbody>
      </table>
      <div class="popup-coords">座標: ${lat.toFixed(7)}, ${lng.toFixed(7)}（事故発生位置）</div>
      <div class="popup-links">
        <a class="popup-link" href="https://www.google.com/maps?q=${lat},${lng}&hl=ja" target="_blank" rel="noopener">🌏 Google Maps</a>
        <a class="popup-link" href="https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}&hl=ja" target="_blank" rel="noopener">📷 Street View</a>
      </div>
    </div>
  `;
}
