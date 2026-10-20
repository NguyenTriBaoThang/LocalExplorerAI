(() => {
  if (window.__mapBotWidgetLoaded) return;
  window.__mapBotWidgetLoaded = true;

  const style = document.createElement('style');
  style.textContent = `
    .mapbot-launcher{position:fixed;right:24px;bottom:24px;z-index:10000;display:flex;align-items:center;gap:10px;border:0;border-radius:999px;padding:13px 18px;background:#167d68;color:#fff;box-shadow:0 8px 28px #10251f40;font:600 15px/1.2 system-ui,sans-serif;cursor:pointer}
    .mapbot-launcher:hover{background:#116653;transform:translateY(-1px)}
    .mapbot-launcher:focus-visible,.mapbot-close:focus-visible,.mapbot-send:focus-visible,.mapbot-prompt:focus-visible,.mapbot-input:focus-visible{outline:3px solid #f2b544;outline-offset:3px}
    .mapbot-launcher-icon{font-size:20px;line-height:1}
    .mapbot-panel{position:fixed;right:24px;bottom:86px;z-index:10000;display:flex;flex-direction:column;width:min(370px,calc(100vw - 32px));height:min(520px,calc(100dvh - 120px));overflow:hidden;border:1px solid #dce8e3;border-radius:18px;background:#fff;box-shadow:0 18px 55px #10251f35;color:#18332c;font:14px/1.45 system-ui,sans-serif}
    .mapbot-panel[hidden]{display:none}
    .mapbot-header{display:flex;align-items:center;gap:11px;padding:15px 16px;background:#167d68;color:#fff}
    .mapbot-avatar{display:grid;place-items:center;width:38px;height:38px;border-radius:50%;background:#ffffff24;font-size:21px}
    .mapbot-title{flex:1;font-size:16px;font-weight:700}.mapbot-status{display:block;margin-top:2px;font-size:12px;font-weight:400;opacity:.85}
    .mapbot-close{width:34px;height:34px;border:0;border-radius:50%;background:transparent;color:#fff;font-size:23px;cursor:pointer}
    .mapbot-messages{flex:1;overflow:auto;padding:16px;background:#f5f8f6;scroll-behavior:smooth}
    .mapbot-message{max-width:88%;margin:0 0 12px;padding:10px 12px;border-radius:14px;white-space:pre-wrap;overflow-wrap:anywhere}
    .mapbot-message.bot{border:1px solid #e3ebe7;border-top-left-radius:4px;background:#fff}
    .mapbot-message.user{margin-left:auto;border-top-right-radius:4px;background:#167d68;color:#fff}
    .mapbot-recommendations{max-width:96%!important;padding:11px!important}
    .mapbot-recommendation{display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid #e7eeea}
    .mapbot-recommendation:last-child{border-bottom:0}
    .mapbot-recommendation-copy{min-width:0;flex:1}
    .mapbot-recommendation a{color:#126c57;font-weight:700;text-decoration:underline;text-underline-offset:2px;overflow-wrap:anywhere}
    .mapbot-recommendation small{display:block;margin-top:3px;color:#64756e;font-size:11px;line-height:1.4}
    .mapbot-recommendation-image{width:76px;height:64px;flex:none;border-radius:9px;background:#e8efeb;object-fit:cover}
    .mapbot-prompts{display:flex;flex-wrap:wrap;gap:7px;margin:4px 0 12px}
    .mapbot-prompt{border:1px solid #b7d8cb;border-radius:999px;padding:7px 10px;background:#fff;color:#145c4b;font:inherit;font-size:12px;cursor:pointer}
    .mapbot-form{display:flex;gap:8px;padding:12px;border-top:1px solid #e3ebe7;background:#fff}
    .mapbot-input{min-width:0;flex:1;border:1px solid #d3dfd9;border-radius:12px;padding:11px 12px;color:#18332c;font:inherit}
    .mapbot-send{border:0;border-radius:12px;padding:0 15px;background:#167d68;color:#fff;font:600 14px system-ui,sans-serif;cursor:pointer}
    .mapbot-send:disabled{opacity:.5;cursor:default}
    @media(max-width:480px){.mapbot-launcher{right:16px;bottom:16px}.mapbot-panel{right:8px;bottom:76px;width:calc(100vw - 16px);height:min(560px,calc(100dvh - 96px))}}
  `;
  document.head.append(style);

  const launcher = document.createElement('button');
  launcher.className = 'mapbot-launcher';
  launcher.type = 'button';
  launcher.setAttribute('aria-label', 'Mở chat với MapBot');
  launcher.setAttribute('aria-expanded', 'false');
  launcher.innerHTML = '<span class="mapbot-launcher-icon" aria-hidden="true">✦</span><span>MapBot</span>';

  const panel = document.createElement('section');
  panel.className = 'mapbot-panel';
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'Chat với MapBot');
  panel.setAttribute('aria-modal', 'false');
  panel.hidden = true;
  panel.innerHTML = `
    <header class="mapbot-header">
      <span class="mapbot-avatar" aria-hidden="true">🗺️</span>
      <div class="mapbot-title">MapBot<span class="mapbot-status">Trợ lý khám phá địa phương</span></div>
      <button class="mapbot-close" type="button" aria-label="Đóng chat">×</button>
    </header>
    <div class="mapbot-messages" aria-live="polite" aria-relevant="additions text"></div>
    <form class="mapbot-form">
      <input class="mapbot-input" type="text" maxlength="500" autocomplete="off" placeholder="Bạn muốn khám phá điều gì?" aria-label="Tin nhắn cho MapBot">
      <button class="mapbot-send" type="submit">Gửi</button>
    </form>`;

  document.body.append(launcher, panel);
  const messages = panel.querySelector('.mapbot-messages');
  const input = panel.querySelector('.mapbot-input');
  const form = panel.querySelector('.mapbot-form');

  function addMessage(text, who) {
    const bubble = document.createElement('div');
    bubble.className = `mapbot-message ${who}`;
    bubble.textContent = text;
    messages.append(bubble);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
  }

  function showWelcome() {
    if (messages.childElementCount) return;
    addMessage('Xin chào! Mình là MapBot. Mình có thể hướng dẫn bạn tìm địa điểm, trải nghiệm và lên kế hoạch khám phá. Giá và chỗ trống cần xem tại thông tin đặt chỗ mới nhất.', 'bot');
    const prompts = document.createElement('div');
    prompts.className = 'mapbot-prompts';
    ['Gợi ý quán ăn', 'Gợi ý quán cà phê', 'Xem thời tiết và AQI'].forEach((label) => {
      const button = document.createElement('button');
      button.className = 'mapbot-prompt';
      button.type = 'button';
      button.textContent = label;
      button.addEventListener('click', () => sendMessage(label));
      prompts.append(button);
    });
    messages.append(prompts);
  }

  function normalizeText(text) {
    return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'd').toLocaleLowerCase('vi').replace(/[^a-z0-9]+/g, ' ').trim();
  }

  function classifyRequest(text) {
    const normalized = normalizeText(text);
    if (/thoi tiet|aqi|khong khi|weather|du bao|troi mua|mua khong|co mua/.test(normalized)) return 'weather';
    if (/dat cho|dat ve|booking|con cho|suc chua|gia tien|bao nhieu tien/.test(normalized)) return 'booking';
    if (/an uong|quan an|nha hang|mon an|di an|\ban\b|food|eat|restaurant/.test(normalized)) return 'food';
    if (/ca phe|cafe|coffee|tra sua/.test(normalized)) return 'coffee';
    if (/lich su|van hoa|bao tang|di san|di tich|museum|culture|tham quan/.test(normalized)) return 'culture';
    if (/thien nhien|cong vien|song sai gon|ngam canh|nature|park/.test(normalized)) return 'nature';
    if (/dia diem|di dau|quan|tim|trai nghiem|kham pha|goi y/.test(normalized)) return 'clarify';
    return 'help';
  }

  function replyTo(text) {
    const kind = classifyRequest(text);
    if (kind === 'weather') {
      return 'Mở Weather AQI Advisor để xem dự báo thời tiết và AQI mới nhất. Nếu bạn cho mình ngày đi, mình có thể giúp kiểm tra thông tin cho ngày đó.';
    }
    if (kind === 'booking') {
      return 'Chọn một địa điểm để mở trang chi tiết trải nghiệm; ở đó có giá, lịch và thông tin chỗ do đối tác cập nhật. MapBot không tự đoán giá hoặc chỗ trống.';
    }
    if (kind === 'clarify') {
      return 'Bạn muốn tìm quán ăn, cà phê, điểm tham quan hay địa điểm ở quận nào?';
    }
    return 'Mình có thể tìm quán ăn, cà phê hoặc điểm tham quan ở TP. Hồ Chí Minh, và tra cứu thời tiết/AQI. Bạn đang muốn tìm loại địa điểm nào?';
  }

  function requestedDistrict(text) {
    const match = normalizeText(text).match(/\b(?:quan|q|district)\s*(\d{1,2})\b/);
    return match ? match[1] : null;
  }

  function matchesDistrict(item, district) {
    if (!district) return true;
    const poi = item.poi || item;
    const location = normalizeText([poi.district, poi.address].filter(Boolean).join(' '));
    return new RegExp(`(^|\\s)(quan\\s*${district}|district\\s*${district}|q\\s*${district})(\\s|$)`).test(location);
  }

  async function loadRecommendations(kind, district) {
    const params = new URLSearchParams({ scope: 'citywide' });
    if (kind === 'food') params.set('intent', 'food');
    else if (kind === 'coffee') params.set('topic', 'cafe');
    else if (kind === 'culture') params.set('intent', 'culture');
    else if (kind === 'nature') params.set('intent', 'relaxation');
    let experiences = [];
    try {
      const response = await fetch(`/api/experiences?${params.toString()}`, { headers: { Accept: 'application/json' } });
      if (response.ok) {
        const payload = await response.json();
        if (Array.isArray(payload)) experiences = payload;
      }
    } catch (_) {
      // Try the public POI directory below if the experience catalog is unavailable.
    }
    const ranked = experiences
      .filter((item) => item && item.poi && item.poi.id && item.poi.name)
      .filter((item) => matchesDistrict(item, district))
      .sort((a, b) => {
        const aRated = (a.rating_count || 0) > 0;
        const bRated = (b.rating_count || 0) > 0;
        if (aRated !== bRated) return aRated ? -1 : 1;
        return (b.rating_average || 0) - (a.rating_average || 0);
      })
      .slice(0, 3);
    if (ranked.length) return ranked;

    const poiResponse = await fetch('/api/pois?scope=citywide', { headers: { Accept: 'application/json' } });
    if (!poiResponse.ok) throw new Error('catalog_unavailable');
    const pois = await poiResponse.json();
    const cues = {
      food: /an uong|restaurant|food|cuisine|quan an|nha hang|mon an/,
      coffee: /cafe|coffee|ca phe|tra sua/,
      culture: /tham quan|museum|culture|lich su|van hoa|di san|di tich|temple/,
      nature: /nature|park|cong vien|thien nhien|song sai gon|ngam canh|relax/,
    };
    return pois
      .filter((poi) => cues[kind].test(normalizeText([poi.category, poi.name, poi.description, ...(poi.tags || [])].join(' '))))
      .filter((poi) => matchesDistrict(poi, district))
      .slice(0, 3);
  }

  function addRecommendations(items, kind, district) {
    const labels = { food: 'quán ăn', coffee: 'quán cà phê', culture: 'điểm tham quan văn hóa', nature: 'điểm thư giãn và thiên nhiên' };
    const bubble = document.createElement('div');
    bubble.className = 'mapbot-message bot mapbot-recommendations';
    const intro = document.createElement('div');
    const area = district ? ` ở Quận ${district}` : ' trong danh mục TP. Hồ Chí Minh';
    intro.textContent = `Mình tìm thấy ${items.length} gợi ý ${labels[kind] || 'địa điểm'}${area}:`;
    bubble.append(intro);
    items.forEach((item) => {
      const poi = item.poi || item;
      const card = document.createElement('div');
      card.className = 'mapbot-recommendation';
      const link = document.createElement('a');
      link.href = `/places/${encodeURIComponent(poi.id)}`;
      link.textContent = poi.name;
      const details = document.createElement('small');
      const parts = [];
      if (poi.district) parts.push(poi.district);
      else if (poi.address) parts.push(poi.address);
      if (item.price_vnd > 0) {
        const cost = Number(item.price_vnd).toLocaleString('vi-VN');
        parts.push(item.price_basis === 'per_person' ? `từ ${cost} ₫/người` : `${cost} ₫`);
      }
      const ratingCount = item.rating_count ?? poi.community_rating_count ?? 0;
      const ratingAverage = item.rating_average ?? poi.community_rating_average;
      if (ratingCount > 0 && ratingAverage != null) parts.push(`★ ${ratingAverage} (${ratingCount} đánh giá)`);
      details.textContent = parts.join(' · ') || 'Mở trang địa điểm để xem thông tin chi tiết';
      const copy = document.createElement('div');
      copy.className = 'mapbot-recommendation-copy';
      copy.append(link, details);
      const imageUrl = recommendationImage(item, poi);
      if (imageUrl) {
        const image = document.createElement('img');
        image.className = 'mapbot-recommendation-image';
        image.src = imageUrl;
        image.alt = `Ảnh ${poi.name}`;
        image.loading = 'lazy';
        image.decoding = 'async';
        image.addEventListener('error', () => image.remove(), { once: true });
        card.append(copy, image);
      } else {
        card.append(copy);
      }
      bubble.append(card);
    });
    const note = document.createElement('small');
    note.textContent = 'Gợi ý lấy từ danh mục địa điểm; giá và giờ mở cửa có thể thay đổi. Mở từng địa điểm để kiểm tra thông tin mới nhất.';
    bubble.append(note);
    messages.append(bubble);
    messages.scrollTop = messages.scrollHeight;
  }

  function recommendationImage(item, poi) {
    const sourcePhoto = Array.isArray(poi.details?.images)
      ? poi.details.images.find((photo) => photo && (photo.local_url || photo.url) && photo.source_url && photo.license)
      : null;
    const candidate = sourcePhoto?.local_url || sourcePhoto?.url
      || (Array.isArray(poi.image_urls) ? poi.image_urls.find((url) => typeof url === 'string' && url.trim()) : null)
      || item.image_url || item.cover_url || poi.photo_url;
    if (typeof candidate !== 'string') return null;
    const value = candidate.trim();
    if (value.startsWith('/') && !value.startsWith('//')) return value;
    try {
      const url = new URL(value, window.location.origin);
      return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null;
    } catch (_) {
      return null;
    }
  }

  async function sendMessage(text) {
    const value = text.trim();
    if (!value) return;
    messages.querySelector('.mapbot-prompts')?.remove();
    addMessage(value, 'user');
    input.value = '';
    const kind = classifyRequest(value);
    if (['food', 'coffee', 'culture', 'nature'].includes(kind)) {
      const pending = addMessage('Đang tìm địa điểm phù hợp trong danh mục…', 'bot');
      const district = requestedDistrict(value);
      form.querySelector('.mapbot-send').disabled = true;
      input.disabled = true;
      try {
        const recommendations = await loadRecommendations(kind, district);
        pending.remove();
        if (recommendations.length) addRecommendations(recommendations, kind, district);
        else addMessage(district
          ? `Mình chưa tìm thấy gợi ý phù hợp ở Quận ${district}. Bạn thử quận khác hoặc bỏ lọc khu vực nhé.`
          : 'Mình chưa tìm thấy địa điểm phù hợp trong danh mục lúc này. Bạn thử đổi sang quán ăn, cà phê hay điểm tham quan nhé.', 'bot');
      } catch (_) {
        pending.textContent = 'Hiện mình chưa tải được danh mục địa điểm. Bạn thử lại sau hoặc mở mục Địa điểm để xem danh sách đang có.';
      } finally {
        form.querySelector('.mapbot-send').disabled = false;
        input.disabled = false;
        messages.scrollTop = messages.scrollHeight;
      }
      return;
    }
    window.setTimeout(() => addMessage(replyTo(value), 'bot'), 180);
  }

  function setOpen(open) {
    panel.hidden = !open;
    launcher.setAttribute('aria-expanded', String(open));
    if (open) {
      showWelcome();
      input.focus();
    } else launcher.focus();
  }

  launcher.addEventListener('click', () => setOpen(panel.hidden));
  panel.querySelector('.mapbot-close').addEventListener('click', () => setOpen(false));
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    sendMessage(input.value);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !panel.hidden) setOpen(false);
  });
})();
