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
  }

  function showWelcome() {
    if (messages.childElementCount) return;
    addMessage('Xin chào! Mình là MapBot. Mình có thể hướng dẫn bạn tìm địa điểm, trải nghiệm và lên kế hoạch khám phá. Giá và chỗ trống cần xem tại thông tin đặt chỗ mới nhất.', 'bot');
    const prompts = document.createElement('div');
    prompts.className = 'mapbot-prompts';
    ['Tìm trải nghiệm phù hợp', 'Xem thời tiết và AQI', 'Cách đặt chỗ'].forEach((label) => {
      const button = document.createElement('button');
      button.className = 'mapbot-prompt';
      button.type = 'button';
      button.textContent = label;
      button.addEventListener('click', () => sendMessage(label));
      prompts.append(button);
    });
    messages.append(prompts);
  }

  function replyTo(text) {
    const normalized = text.toLocaleLowerCase('vi');
    if (/thời tiết|aqi|mưa|không khí/.test(normalized)) {
      return 'Bạn có thể mở mục Weather AQI Advisor để xem dữ liệu thời tiết và chất lượng không khí mới nhất. Hãy kiểm tra thời điểm cập nhật trước khi khởi hành.';
    }
    if (/đặt chỗ|đặt vé|booking|còn chỗ|sức chứa|giá/.test(normalized)) {
      return 'Hãy mở trang chi tiết trải nghiệm để xem giá, lịch và số chỗ còn được đối tác xác nhận. MapBot không tự suy đoán giá hoặc tình trạng chỗ.';
    }
    if (/địa điểm|đi đâu|quận|tìm|trải nghiệm|khám phá/.test(normalized)) {
      return 'Bạn hãy dùng mục khám phá/tìm kiếm trên bản đồ để lọc địa điểm và trải nghiệm. Nếu cho mình biết quận, sở thích và khoảng thời gian, mình có thể giúp bạn xác định tiêu chí tìm phù hợp.';
    }
    return 'Mình có thể hướng dẫn tìm địa điểm và trải nghiệm, xem Weather AQI Advisor hoặc cách kiểm tra thông tin đặt chỗ. Bạn đang muốn khám phá khu vực hay hoạt động nào?';
  }

  function sendMessage(text) {
    const value = text.trim();
    if (!value) return;
    messages.querySelector('.mapbot-prompts')?.remove();
    addMessage(value, 'user');
    input.value = '';
    window.setTimeout(() => addMessage(replyTo(value), 'bot'), 250);
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
