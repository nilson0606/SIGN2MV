// SIGN2MV tutorial film: segment recording, shortest flow (zh-TW).
// Drives the real sing page in the demo environment; captions, spotlight and cursor are drawn in the page.
// KEYS=1  -> only key screenshots (/tmp/tut_keys); RECORD=1 -> also capture frames (/tmp/tut_frames) + frames.json
const { chromium } = require('playwright');
const fs = require('fs');
const RECORD = !!process.env.RECORD;
const KEYDIR = '/tmp/tut_keys', FRAMEDIR = '/tmp/tut_frames';
const W = 960, H = 540, CAP = 124, DSF = Number(process.env.DSF || 2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  fs.rmSync(KEYDIR, { recursive: true, force: true }); fs.mkdirSync(KEYDIR, { recursive: true });
  if (RECORD) { fs.rmSync(FRAMEDIR, { recursive: true, force: true }); fs.mkdirSync(FRAMEDIR, { recursive: true }); }
  const b = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--force-color-profile=srgb',
    `--force-device-scale-factor=${DSF}`, `--window-size=${W},${H}`, '--hide-scrollbars'] });   // a real scale factor: the screencast then gives full-size frames
  const ctx = await b.newContext({ viewport: null, permissions: ['microphone'], locale: 'zh-TW' });
  const p = await ctx.newPage();
  p.on('pageerror', (e) => console.log('PAGEERROR', e.message));
  await p.goto('http://127.0.0.1:9713/sing/index.html'); await sleep(2500);

  // ---------- overlay ----------
  await p.addStyleTag({ content: `
    #tut-cap{position:fixed;left:0;right:0;top:0;height:${CAP}px;z-index:2147483600;background:linear-gradient(#0a1120,#101c33);border-bottom:3px solid #fbbf24;display:flex;align-items:center;gap:20px;padding:0 30px;box-sizing:border-box;font-family:"Noto Sans CJK TC","Noto Sans CJK HK",sans-serif;pointer-events:none}
    #tut-num{flex:none;min-width:66px;height:66px;padding:0 6px;box-sizing:border-box;border-radius:33px;background:#fbbf24;color:#1a1205;font-size:38px;font-weight:800;display:flex;align-items:center;justify-content:center}
    #tut-num.tip{font-size:22px;padding:0 16px}
    #tut-main{color:#fff;font-size:27px;font-weight:700;line-height:1.3}
    #tut-sub{color:#cbd5e1;font-size:17px;margin-top:6px;line-height:1.35}
    #tut-ring{position:fixed;z-index:2147483500;border:4px solid #ff4d4f;border-radius:12px;box-shadow:0 0 0 9999px rgba(3,7,18,.6);pointer-events:none;transition:left .3s,top .3s,width .3s,height .3s;display:none}
    #tut-ring.soft{box-shadow:0 0 0 9999px rgba(3,7,18,.28)}
    #tut-ring.pulse{animation:tutp .45s}
    @keyframes tutp{0%{transform:scale(1)}40%{transform:scale(.93)}100%{transform:scale(1)}}
    #tut-cur{position:fixed;z-index:2147483550;width:30px;height:30px;pointer-events:none;transition:left .55s ease,top .55s ease;left:${W / 2}px;top:${H - 60}px;display:none}
    #tut-speed{position:fixed;right:18px;bottom:14px;z-index:2147483600;background:#fbbf24;color:#1a1205;font:700 19px "Noto Sans CJK TC",sans-serif;padding:6px 16px;border-radius:999px;display:none;pointer-events:none}
    #tut-card{position:fixed;inset:0;z-index:2147483647;background:radial-gradient(ellipse at 30% 15%,#1d2f55,#070b14 72%);display:none;flex-direction:column;align-items:center;justify-content:center;font-family:"Noto Sans CJK TC","Noto Sans CJK HK",sans-serif;color:#fff;pointer-events:none;text-align:center}
    #tut-card h1{font-size:54px;margin:0 0 14px;letter-spacing:2px}
    #tut-card h2{font-size:24px;font-weight:500;color:#fbbf24;margin:0 0 26px}
    #tut-card p{font-size:20px;color:#cbd5e1;margin:4px 0}
    #tut-card ol{font-size:22px;line-height:1.75;text-align:left;margin:0;padding-left:1.4em}
    #tut-card ol b{color:#fbbf24}
  ` });
  await p.evaluate(() => {
    const mk = (id, html = '') => { const d = document.createElement('div'); d.id = id; d.innerHTML = html; document.body.append(d); return d; };
    mk('tut-ring'); mk('tut-speed'); mk('tut-card');
    mk('tut-cap', '<div id="tut-num"></div><div><div id="tut-main"></div><div id="tut-sub"></div></div>');
    mk('tut-cur', '<svg viewBox="0 0 24 24" width="30" height="30"><path d="M4 2l15 9-7 1.6L9 20z" fill="#fff" stroke="#111" stroke-width="1.5" stroke-linejoin="round"/></svg>');
    window.__tut = { sels: [], pad: 8 };
    const tick = () => {
      const ring = document.getElementById('tut-ring'), t = window.__tut;
      const rs = t.sels.map((s) => document.querySelector(s)).filter((e) => e && e.getClientRects().length).map((e) => e.getBoundingClientRect());
      if (rs.length) {
        const l = Math.min(...rs.map((r) => r.left)) - t.pad, tp = Math.min(...rs.map((r) => r.top)) - t.pad;
        const r = Math.max(...rs.map((r) => r.right)) + t.pad, bt = Math.max(...rs.map((r) => r.bottom)) + t.pad;
        Object.assign(ring.style, { left: l - 4 + 'px', top: tp - 4 + 'px', width: r - l + 'px', height: bt - tp + 'px' });
      }
    };
    window.addEventListener('scroll', tick, { passive: true });
    setInterval(tick, 200);
    window.__tutTick = tick;
  });

  // ---------- recorder ----------
  const frames = [], marks = [];
  let speed = 1, keep = 2, n = 0;
  const now = () => Date.now() / 1000;
  let cdp = null;
  const cast = (nth) => cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: W * DSF, maxHeight: H * DSF, everyNthFrame: nth });
  if (RECORD) {
    cdp = await ctx.newCDPSession(p);
    cdp.on('Page.screencastFrame', async (f) => {
      cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
      const file = `${FRAMEDIR}/f${String(n++).padStart(6, '0')}.jpg`;
      fs.writeFile(file, Buffer.from(f.data, 'base64'), () => {});
      frames.push({ file, ts: now() });
    });
    await cast(2);
  }
  const mark = (o) => marks.push({ ts: now(), ...o });
  const scene = (name) => { mark({ scene: name }); console.log(`--- scene ${name}`); };
  const setSpeed = async (s) => {
    speed = s; mark({ speed: s });
    const nth = s >= 8 ? 12 : s >= 3 ? 6 : 2;       // fewer frames while fast-forwarding (also less load on the page)
    if (cdp && nth !== keep) { keep = nth; await cdp.send('Page.stopScreencast').catch(() => {}); await cast(nth); }
    await p.evaluate((s) => { const e = document.getElementById('tut-speed'); e.style.display = s > 1 ? 'block' : 'none'; e.textContent = `快轉 ×${s}`; }, s);
  };
  let keyN = 0;
  const key = async (name) => { await p.screenshot({ path: `${KEYDIR}/${String(++keyN).padStart(2, '0')}_${name}.jpg`, type: 'jpeg', quality: 90 }); };

  // ---------- helpers ----------
  const cap = (num, main, sub = '') => p.evaluate(([num, main, sub]) => {
    const e = document.getElementById('tut-num'); e.textContent = num; e.className = /\d/.test(num) ? '' : 'tip';
    document.getElementById('tut-main').textContent = main; document.getElementById('tut-sub').textContent = sub;
  }, [String(num), main, sub]);
  const ringOff = () => p.evaluate(() => { window.__tut.sels = []; document.getElementById('tut-ring').style.display = 'none'; });
  const spot = async (sels, { soft = false, pad = 8, scroll = true, bottom = false } = {}) => {
    sels = [].concat(sels);
    if (scroll) {
      const moved = await p.evaluate(([sels, CAP, H, bottom]) => {
        const rs = sels.map((s) => document.querySelector(s)).filter((e) => e && e.getClientRects().length).map((e) => e.getBoundingClientRect());
        if (!rs.length) return false;
        const top = Math.min(...rs.map((r) => r.top)), bottom_ = Math.max(...rs.map((r) => r.bottom));
        const want = CAP + (H - CAP) / 2 - (bottom_ - top) / 2;            // centre in the area below the caption
        const dy = bottom ? bottom_ - (H - 26) : top - Math.max(CAP + 16, want);
        if (Math.abs(dy) < 24) return false;
        document.getElementById('tut-ring').style.display = 'none';
        window.scrollBy({ top: dy, behavior: 'smooth' });
        return true;
      }, [sels, CAP, H, bottom]);
      if (moved) await sleep(900);
    }
    await p.evaluate(([sels, soft, pad]) => {
      window.__tut.sels = sels; window.__tut.pad = pad;
      const r = document.getElementById('tut-ring'); r.className = soft ? 'soft' : ''; r.style.display = 'block';
      window.__tutTick();
    }, [sels, soft, pad]);
    await sleep(450);
  };
  const cursorTo = async (sel) => {
    await p.evaluate((sel) => {
      const r = document.querySelector(sel).getBoundingClientRect(), c = document.getElementById('tut-cur');
      c.style.display = 'block'; c.style.left = r.left + r.width / 2 - 4 + 'px'; c.style.top = r.top + r.height / 2 - 2 + 'px';
    }, sel);
    await sleep(700);
  };
  const press = async (sel) => {
    await cursorTo(sel);
    await p.evaluate(() => { const r = document.getElementById('tut-ring'); r.classList.remove('pulse'); void r.offsetWidth; r.classList.add('pulse'); });
    await sleep(180);
    await p.locator(sel).click({ force: true });      // the ring and caption never take the click
    await sleep(350);
  };
  const card = (html) => p.evaluate((html) => { const c = document.getElementById('tut-card'); c.innerHTML = html; c.style.display = html ? 'flex' : 'none'; }, html);
  const vtime = () => p.evaluate(() => document.querySelector('video').currentTime);
  const status = () => p.locator('#segment-status').innerText();
  // wait until the take is saved; false when the capture broke (the page says so and asks to record again)
  const saved = async () => {
    await p.waitForFunction(() => document.querySelector('#segment-stop').disabled && !document.querySelector('#segment-record').disabled
      && !/正在保存/.test(document.querySelector('#segment-status').innerText), null, { timeout: 90000 });
    const s = await status(); console.log('   status:', s.slice(0, 60));
    return !/中斷|失敗|不連續/.test(s);
  };

  if (/開啟/.test(await p.locator('#motion-toggle').innerText())) await p.locator('#motion-toggle').click();
  console.log('motion:', await p.locator('#motion-toggle').innerText());

  // ================= film =================
  scene('title');
  await card('<h1>分段錄音　最短流程</h1><h2>SIGN2MV 唱錄 · 一段一段唱，再接成整首</h2><p>只要按 7 個地方，其他按鈕先不用管</p>');
  await sleep(600); await key('title'); await sleep(3200);
  await cap(1, '選歌，按「載入 MV」', '在「已匯入的 MV」選單選歌');
  await p.evaluate(() => window.scrollTo(0, 0));
  await card('');

  scene('s1_load');
  await spot('#local-media-saved'); await sleep(900);
  await cursorTo('#local-media-saved'); await p.selectOption('#local-media-saved', { index: 1 }); await sleep(1100);
  await spot('#local-media-load'); await key('s1_load');
  await press('#local-media-load');
  await p.waitForFunction(() => /已載入/.test(document.querySelector('#player-section').innerText), null, { timeout: 20000 });
  await cap(1, '選歌，按「載入 MV」', '第一次唱這首歌：還要按頁面下方的「準備歌曲基準」，等它完成');
  await spot(['#local-media-saved', '#local-media-load', 'video'], { soft: true }); await sleep(600); await key('s1_loaded'); await sleep(2600);

  scene('s2_mic');
  await cap(2, '戴上耳機，按「開啟麥克風」', '在頁面右邊的「即時音高與收音」');
  await spot('#mic-start'); await sleep(700); await key('s2_mic');
  await press('#mic-start'); await sleep(1500);
  await cap(2, '戴上耳機，按「開啟麥克風」', '出現「收音中」就可以了');
  await spot('#voice-section .section-top, #voice-section h2', { soft: true }).catch(() => {});
  await sleep(500); await key('s2_mic_on'); await sleep(1800);

  scene('s3_open');
  await cap(3, '往下捲到「正式錄音」，按「開啟錄音模式」', '');
  await spot('#segment-open'); await sleep(700); await key('s3_open');
  await press('#segment-open'); await sleep(900);
  await spot(['#segment-heading', '#segment-mode-label'], { soft: true }); await sleep(400); await key('s3_opened'); await sleep(1500);

  scene('s4_split');
  await cap(4, '按「播放／暫停影片」，聽到要換段的地方按「在此分段」', '不用先決定幾段；按錯了可以按「復原分界」');
  await spot(['#segment-play', '#segment-split', '#segment-undo'], { soft: true, bottom: true }); await sleep(1200); await key('s4_buttons');
  await press('#segment-play');
  await setSpeed(6);
  for (const t of [16, 32, 48]) {
    await p.waitForFunction((t) => document.querySelector('video').currentTime >= t - 1.6, t, { timeout: 40000 });
    await setSpeed(1);
    await cursorTo('#segment-split');
    await p.waitForFunction((t) => document.querySelector('video').currentTime >= t - 0.25, t, { timeout: 10000 });
    await p.evaluate(() => { const r = document.getElementById('tut-ring'); r.classList.remove('pulse'); void r.offsetWidth; r.classList.add('pulse'); });
    await p.locator('#segment-split').click({ force: true });
    console.log('split at', (await vtime()).toFixed(2));
    await sleep(700);
    if (t !== 48) await setSpeed(6);
  }
  await press('#segment-play');
  await cap(4, '按「播放／暫停影片」，聽到要換段的地方按「在此分段」', '分好了：下方的時間軸變成 4 段');
  await p.evaluate(() => { document.getElementById('tut-cur').style.display = 'none'; });
  await spot(['#segment-timeline', '#segment-part']); await sleep(600); await key('s4_timeline'); await sleep(2400);

  scene('s5_record');
  await cap(5, '選要錄的段落，按「錄製第 1 段」', '可以先按「循環練唱本段」練習');
  await p.selectOption('#segment-part', { index: 0 }); await sleep(300);
  await spot('#segment-part'); await sleep(1300);
  let pending = null;                      // start of a take whose capture broke: left out of the film up to the next press
  const record = async (first) => {
    const t0 = now();
    await press('#segment-record');
    if (pending !== null) { mark({ drop: [pending, now()] }); pending = null; }
    await sleep(1300);                     // the page itself jumps to the player
    await p.evaluate(() => { document.getElementById('tut-cur').style.display = 'none'; });
    await spot(['video'], { soft: true, scroll: false, pad: 4 });
    return t0;
  };
  for (let attempt = 1; ; attempt++) {
    await spot('#segment-record'); await sleep(500); if (attempt === 1) await key('s5_record');
    const t0 = await record();
    await cap(5, '畫面會自動跳到影片：看著歌詞跟著唱', '唱到段尾會自動保存');
    console.log('   scrolled to the player:', await p.evaluate(() => { const r = document.querySelector('video').getBoundingClientRect(); return r.top > 0 && r.bottom < innerHeight + 200; }));
    await sleep(2600); await key(`s5_recording${attempt}`);
    await setSpeed(4);
    const ok = await saved();
    await setSpeed(1);
    if (ok) break;
    pending = t0;
    console.log(`   segment 1: capture broke, recording it again (attempt ${attempt + 1})`);
    if (attempt >= 4) throw new Error('capture keeps breaking');
    await cap(5, '選要錄的段落，按「錄製第 1 段」', '可以先按「循環練唱本段」練習');
  }
  await cap(5, '唱完自動保存', '不滿意？再按一次「錄製第 1 段」就是重錄，每次都會保留');
  await spot(['#segment-record', '#segment-stop', '#segment-status'], { soft: true });
  await sleep(500); await key('s5_saved'); await sleep(2800);

  scene('s5_rest');
  await cap(5, '其餘各段一樣：選段落 → 按錄製', '每一段都可以重錄很多次');
  await sleep(1200);
  for (const seg of [1, 2, 3, 0]) {           // the last one is a second take of segment 1
    for (let attempt = 1; ; attempt++) {
      await setSpeed(attempt === 1 ? 3 : 12);
      await spot('#segment-part'); await p.selectOption('#segment-part', { index: seg }); await sleep(700);
      await spot('#segment-record', { scroll: false });
      const t0 = await record();
      await sleep(400);
      await setSpeed(12);
      if (await saved()) break;
      pending = t0;
      console.log(`   segment ${seg + 1}: capture broke, recording it again (attempt ${attempt + 1})`);
      if (attempt >= 4) throw new Error('capture keeps breaking');
    }
  }
  await setSpeed(1);
  await spot(['#segment-timeline', '#segment-part'], { soft: true }); await sleep(700); await key('s5_all_done'); await sleep(1100);

  scene('tip');
  await cap('提示', '同一段錄了好幾次？', '展開右邊的「挑選本段演唱版本」，選最滿意的那一次');
  await p.selectOption('#segment-part', { index: 0 }); await sleep(400);
  await p.evaluate(() => { document.getElementById('tut-cur').style.display = 'none'; document.querySelector('#segment-versions-panel').open = true; });
  await sleep(500);
  console.log('takes of segment 1:', await p.locator('#segment-take option').allTextContents());
  await spot(['#segment-versions-panel summary', '#segment-take']); await sleep(600); await key('tip_versions'); await sleep(3200);

  scene('s6_compose');
  await cap(6, '按「試合完整一版」，把各段接成整首', '預設是人聲＋伴樂');
  await p.evaluate(() => { document.querySelector('#segment-output-panel').open = true; });
  await spot('#segment-compose'); await sleep(700); await key('s6_compose');
  await press('#segment-compose');
  await p.waitForFunction(() => !document.querySelector('#segment-export').disabled, null, { timeout: 60000 });
  await cap(6, '按「試合完整一版」，把各段接成整首', '完成後出現播放器，先聽聽看接得順不順');
  await p.evaluate(() => { document.getElementById('tut-cur').style.display = 'none'; });
  console.log('audio visible:', await p.evaluate(() => { const a = document.querySelector('#segment-audio'); return !a.hidden && a.getClientRects().length > 0; }));
  await spot(['#segment-compose', '#segment-audio'], { soft: true }); await sleep(600); await key('s6_composed'); await sleep(2600);

  scene('s7_save');
  await cap(7, '滿意就按「存到錄音後處理」', '成品會存進「錄音後處理」；也可以按「下載試合 WAV」');
  await spot('#segment-export'); await sleep(700); await key('s7_save');
  await press('#segment-export');
  await p.waitForFunction(() => /已存到錄音後處理/.test(document.querySelector('#segment-output-panel').innerText), null, { timeout: 30000 });
  await p.evaluate(() => { document.getElementById('tut-cur').style.display = 'none'; });
  await sleep(700); await key('s7_saved'); await sleep(2600);

  scene('end');
  await card('<h2>分段錄音　7 個步驟</h2><ol><li>選歌，按 <b>載入 MV</b></li><li>戴耳機，按 <b>開啟麥克風</b></li><li>按 <b>開啟錄音模式</b></li><li><b>播放／暫停影片</b> → 換段處按 <b>在此分段</b></li><li>選段落，按 <b>錄製第 N 段</b>（可重錄）</li><li>按 <b>試合完整一版</b></li><li>按 <b>存到錄音後處理</b></li></ol><p style="margin-top:22px">更詳細的說明：唱錄頁上方的「說明 ↗」</p>');
  await sleep(600); await key('end'); await sleep(6500);
  mark({ end: true });

  if (RECORD) { await sleep(300); fs.writeFileSync('/tmp/tut_frames.json', JSON.stringify({ frames, marks })); console.log('frames', frames.length); }
  await b.close();
})();
