const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

function attachLinkingSiteRoutes(app, deps = {}) {
  const {
    dataDir = process.cwd(),
    normalizePhone = (value) => String(value || '').replace(/\D/g, ''),
    buildSettingsPageHTML = () => '<!doctype html><html><body><h1>Settings</h1></body></html>',
    handlePairingCodeApiRequest,
    getAllLinkedPhones = () => [],
    getAllUserIds = () => [],
    buildPairingApiDescriptor = () => ({ endpoint: '/api/pairing', route: '/api/pairing', settingsPage: '/settings', website: '' }),
    getSummaryExtras = () => ({}),
    siteName = 'موقع الربط',
    routeBase = '/linking-site',
    aliases: aliasInput = [],
    adminPassword = ''
  } = deps;

  const COMMENTS_FILE = path.join(dataDir, 'linking-site-comments.json');
  const PUBLIC_DIR = path.resolve(__dirname, '..', 'public');
  const aliases = Array.from(new Set([routeBase, '/Freebot', ...(Array.isArray(aliasInput) ? aliasInput : [])]));

  function ensureCommentsFile() {
    fs.mkdirSync(path.dirname(COMMENTS_FILE), { recursive: true });
    if (!fs.existsSync(COMMENTS_FILE)) {
      fs.writeFileSync(COMMENTS_FILE, '[]\n', 'utf8');
    }
  }

  function readComments() {
    try {
      ensureCommentsFile();
      const parsed = JSON.parse(fs.readFileSync(COMMENTS_FILE, 'utf8'));
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  }

  function writeComments(comments) {
    ensureCommentsFile();
    fs.writeFileSync(COMMENTS_FILE, JSON.stringify(Array.isArray(comments) ? comments : [], null, 2));
  }

  function sortComments(comments) {
    return [...comments].sort((a, b) => {
      const pinDiff = Number(Boolean(b.pinned)) - Number(Boolean(a.pinned));
      if (pinDiff) return pinDiff;
      return Date.parse(b.createdAt || 0) - Date.parse(a.createdAt || 0);
    });
  }

  function getSummaryPayload() {
    const linkedPhones = Array.isArray(getAllLinkedPhones()) ? getAllLinkedPhones() : [];
    const users = Array.isArray(getAllUserIds()) ? getAllUserIds() : [];
    const pairing = buildPairingApiDescriptor('');
    const extras = typeof getSummaryExtras === 'function' ? (getSummaryExtras() || {}) : {};
    return {
      success: true,
      siteName,
      activeBots: linkedPhones.length,
      totalLinkedNumbers: linkedPhones.length,
      totalUsers: users.length,
      route: routeBase,
      routes: extras.routes || {},
      settingsUrl: `${routeBase}/settings`,
      pairing,
      commandSectionsCount: commandSections.length,
      commandEntriesCount: commandSections.reduce((sum, section) => sum + (Array.isArray(section.rows) ? section.rows.length : 0), 0),
      ...extras,
      generatedAt: new Date().toISOString()
    };
  }

  function getAdminPassword() {
    return String(adminPassword || process.env.LINKING_SITE_ADMIN_PASS || process.env.SITE_PASSWORD || '').trim();
  }

  function isAdminAuthorized(req) {
    const expected = getAdminPassword();
    if (!expected) return false;
    const provided = String(
      req.body?.password ||
      req.query?.password ||
      req.headers['x-admin-password'] ||
      ''
    ).trim();
    return Boolean(provided) && provided === expected;
  }

  function formatDateTime(date = new Date()) {
    try {
      return {
        date: date.toLocaleDateString('ar-EG', { year: 'numeric', month: '2-digit', day: '2-digit' }),
        time: date.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })
      };
    } catch (_) {
      return { date: date.toISOString().slice(0, 10), time: date.toISOString().slice(11, 19) };
    }
  }

  const commandSections = [
    {
      title: 'أوامر التحميل',
      rows: [
        ['.song', '.song Shape of You', 'تنزيل ملف MP3'],
        ['.video', '.video Imagine Dragons', 'تنزيل ملف MP4'],
        ['.tiktok', '.tiktok <url>', 'تنزيل تيك توك'],
        ['.facebook', '.facebook <url>', 'تنزيل فيديو فيسبوك'],
        ['.spotify', '.spotify <name>', 'جلب من سبوتيفاي']
      ]
    },
    {
      title: 'أوامر التحويل',
      rows: [
        ['.sticker', '.sticker', 'تحويل صورة إلى ملصق'],
        ['.tts', '.tts مرحبا', 'تحويل النص إلى صوت'],
        ['.emojimix', '.emojimix 😎+🔥', 'دمج الإيموجي'],
        ['.url', '.url', 'استخراج رابط الوسائط'],
        ['.translate', '.translate hello | ar', 'الترجمة']
      ]
    },
    {
      title: 'أوامر الإدارة',
      rows: [
        ['.pair', '.pair 9677XXXXXXX', 'استخراج كود الربط'],
        ['.settings', '.settings', 'عرض الإعدادات الحالية'],
        ['.alive', '.alive', 'فحص حالة البوت'],
        ['.ping', '.ping', 'قياس سرعة الاستجابة'],
        ['.tagall', '.tagall', 'منشن للجميع']
      ]
    }
  ];

  function buildPageHTML(basePath = routeBase) {
    const config = JSON.stringify({
      siteName,
      basePath,
      settingsUrl: `${basePath}/settings`,
      pairApiUrl: '/api/pairing',
      qrUrl: '/api/qr',
      summaryUrl: '/api/linking-site/summary',
      commentsUrl: '/api/linking-site/comments',
      commentPostUrl: '/api/linking-site/comment',
      reactUrl: '/api/linking-site/react',
      replyUrl: '/api/linking-site/reply',
      pinUrl: '/api/linking-site/pin'
    });

    const tableRows = commandSections.map((section) => {
      const rows = section.rows.map((row) => `<tr><td class="command">${row[0]}</td><td class="example">${row[1]}</td><td class="desc">${row[2]}</td></tr>`).join('');
      return `<tr><td colspan="3" class="section-head">${section.title}</td></tr>${rows}`;
    }).join('');

    return `<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${siteName} | KnightBot MD</title>
  <style>
    :root {
      --bg-1:#071018; --bg-2:#101827; --glass:rgba(255,255,255,.10); --glass-2:rgba(255,255,255,.14);
      --line:rgba(255,255,255,.16); --text:#eef6ff; --muted:#bfd0e4; --brand:#49c6ff; --brand-2:#6ee7f9;
      --accent:#60a5fa; --ok:#34d399; --warn:#f59e0b; --danger:#f87171; --shadow:0 18px 42px rgba(0,0,0,.34);
    }
    *{box-sizing:border-box} html,body{margin:0;padding:0}
    body{
      font-family:Tahoma,Arial,sans-serif; color:var(--text); min-height:100vh; overflow-x:hidden;
      background:
        radial-gradient(circle at top right, rgba(73,198,255,.20), transparent 22%),
        radial-gradient(circle at bottom left, rgba(96,165,250,.16), transparent 20%),
        linear-gradient(145deg, var(--bg-1), var(--bg-2));
    }
    body::before{
      content:''; position:fixed; inset:0; pointer-events:none;
      background:linear-gradient(180deg, rgba(255,255,255,.05), transparent 20%, transparent 80%, rgba(255,255,255,.03));
    }
    .overlay{position:fixed; inset:0; background:rgba(0,0,0,.48); opacity:0; visibility:hidden; transition:.25s; z-index:20}
    .overlay.visible{opacity:1; visibility:visible}
    .sidebar{
      position:fixed; top:0; left:0; height:100%; width:0; overflow:hidden; z-index:30; transition:.28s;
      background:rgba(10,14,22,.90); backdrop-filter:blur(18px); border-right:1px solid rgba(255,255,255,.08); box-shadow:var(--shadow)
    }
    .sidebar-inner{width:320px; max-width:92vw; padding:18px 16px 28px}
    .sidebar h3,.sidebar h4{margin:0}
    .sidebar .brand{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
    .sidebar .brand-badge{padding:8px 12px;border-radius:999px;background:rgba(73,198,255,.12);border:1px solid rgba(73,198,255,.25);font-size:13px;color:#c9f3ff}
    .side-card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:14px;margin-top:12px}
    .side-list{display:grid;gap:10px;margin-top:10px}
    .side-item{display:flex;justify-content:space-between;gap:12px;font-size:14px;color:var(--muted)}
    .side-item strong{color:var(--text)}
    .side-btns{display:grid;gap:10px;margin-top:12px}
    .side-btn,.action-btn,.ghost-btn,.primary-btn,.comment-btn,.mini-btn{border:none;cursor:pointer;border-radius:12px;padding:12px 14px;font-weight:700;font-family:inherit;transition:.2s}
    .side-btn,.mini-btn{background:rgba(255,255,255,.06);color:var(--text);border:1px solid rgba(255,255,255,.1)}
    .side-btn:hover,.mini-btn:hover,.ghost-btn:hover{transform:translateY(-1px);background:rgba(255,255,255,.10)}
    .page{max-width:1100px;margin:0 auto;padding:18px 16px 50px;position:relative;z-index:1}
    .topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}
    .menu-btn{background:var(--glass);color:var(--text);border:1px solid var(--line);border-radius:999px;padding:10px 16px;cursor:pointer;backdrop-filter:blur(10px)}
    .brand-pill{display:inline-flex;align-items:center;gap:10px;padding:12px 18px;background:var(--glass);border:1px solid var(--line);border-radius:999px;backdrop-filter:blur(10px);box-shadow:var(--shadow)}
    .hero,.panel,.desc-card,.comment-box,.comments-list,.components{background:var(--glass);border:1px solid var(--line);backdrop-filter:blur(16px);box-shadow:var(--shadow);border-radius:22px}
    .hero{padding:22px;margin-bottom:18px}
    .hero-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:18px;align-items:stretch}
    .hero h1{margin:0 0 10px;font-size:clamp(28px,4vw,42px)}
    .hero p{margin:0;color:var(--muted);line-height:1.9}
    .stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:18px}
    .stat{padding:14px;border-radius:16px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);text-align:center}
    .stat .value{font-size:24px;font-weight:800;color:#fff}
    .stat .label{font-size:12px;color:var(--muted);margin-top:4px}
    .hero-banner{display:flex;align-items:center;justify-content:center;min-height:100%;padding:18px;border-radius:20px;background:linear-gradient(145deg, rgba(73,198,255,.16), rgba(255,255,255,.05));border:1px solid rgba(73,198,255,.18);position:relative;overflow:hidden}
    .hero-banner::before{content:'';position:absolute;inset:auto -10% -35% auto;width:190px;height:190px;background:radial-gradient(circle, rgba(110,231,249,.28), transparent 70%)}
    .banner-box{width:100%;max-width:420px;padding:18px;border-radius:18px;background:rgba(7,16,24,.44);border:1px solid rgba(255,255,255,.08)}
    .banner-box .kicker{font-size:12px;color:#a9e6ff;letter-spacing:.12em;text-transform:uppercase;margin-bottom:10px}
    .banner-box .title{font-size:26px;font-weight:800;line-height:1.4}
    .banner-box .sub{margin-top:10px;color:var(--muted);line-height:1.8;font-size:14px}
    .button-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}
    .action-btn{background:rgba(255,255,255,.07);color:#fff;border:1px solid rgba(255,255,255,.1);min-height:74px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px}
    .action-btn strong{font-size:15px}
    .action-btn span{font-size:12px;color:#d5e6f5}
    .action-btn.primary{background:linear-gradient(135deg, rgba(59,130,246,.86), rgba(6,182,212,.80));border-color:rgba(125,211,252,.30)}
    .action-btn.success{background:linear-gradient(135deg, rgba(34,197,94,.86), rgba(16,185,129,.76));border-color:rgba(110,231,183,.28)}
    .action-btn.warn{background:linear-gradient(135deg, rgba(245,158,11,.86), rgba(249,115,22,.76));border-color:rgba(253,186,116,.28)}
    .action-btn:hover,.primary-btn:hover,.comment-btn:hover{transform:translateY(-2px)}
    .panel{padding:18px;margin-bottom:18px}
    .panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}
    .panel-title{font-size:20px;font-weight:800}
    .pill{padding:8px 12px;border-radius:999px;background:rgba(73,198,255,.10);border:1px solid rgba(73,198,255,.22);font-size:12px;color:#bfefff}
    .api-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
    .api-card{padding:14px;border-radius:16px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08)}
    .api-card small{display:block;color:var(--muted);margin-bottom:6px}
    .api-card code{display:block;word-break:break-all;font-size:12px;color:#fff;line-height:1.7}
    .desc-card,.comment-box,.comments-list,.components{padding:20px;margin-bottom:18px}
    .desc-card p,.components p{color:var(--muted);line-height:1.95}
    .cards-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:16px}
    .component-card{padding:16px;border-radius:16px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);text-align:center}
    .avatar{width:56px;height:56px;border-radius:50%;display:grid;place-items:center;margin:0 auto 10px;background:linear-gradient(135deg, rgba(59,130,246,.8), rgba(14,165,233,.8));font-size:22px;font-weight:800}
    .component-card h4{margin:6px 0 2px}.component-card small{color:var(--muted)}
    .cmd-btn,.primary-btn,.comment-btn{background:linear-gradient(135deg,#3b82f6,#06b6d4);color:#fff}
    .ghost-btn{background:rgba(255,255,255,.06);color:#ccefff;border:1px solid rgba(255,255,255,.10)}
    .primary-btn,.comment-btn{padding:12px 16px}
    .input, textarea{width:100%;padding:12px 14px;border-radius:14px;border:1px solid rgba(255,255,255,.12);background:rgba(0,0,0,.18);color:#fff;font-family:inherit}
    textarea{min-height:110px;resize:vertical}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .comment{background:rgba(255,255,255,.05);padding:14px;border-radius:14px;border:1px solid rgba(255,255,255,.08);margin-bottom:12px;position:relative}
    .comment p{margin:10px 0 12px;color:#edf7ff;line-height:1.8;white-space:pre-wrap}
    .comment small{color:var(--muted)}
    .reacts{display:flex;flex-wrap:wrap;gap:8px;font-size:14px;color:#dbeeff}
    .react-chip{cursor:pointer;padding:6px 10px;border-radius:999px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08)}
    .meta-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
    .admin-link{font-size:12px;color:#aadfff;cursor:pointer}
    .pinned{position:absolute;top:12px;left:12px}
    footer{padding:24px 10px;color:#adc6da;text-align:center;font-size:14px}
    .popup-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.58);backdrop-filter:blur(4px);z-index:40;padding:20px;overflow:auto}
    .popup-overlay.show{display:block}
    .popup-content{margin:30px auto;width:100%;max-width:980px;background:rgba(9,14,22,.84);border-radius:18px;box-shadow:var(--shadow);border:1px solid rgba(255,255,255,.08);backdrop-filter:blur(16px);overflow:hidden}
    .popup-header{display:flex;align-items:center;justify-content:space-between;padding:16px 18px;border-bottom:1px solid rgba(255,255,255,.06)}
    .popup-body{padding:16px 18px;overflow:auto}
    .close-btn{background:transparent;color:#fff;border:1px solid rgba(255,255,255,.12);padding:8px 12px;border-radius:10px;cursor:pointer}
    table{width:100%;border-collapse:collapse;color:#fff;font-size:14px} th,td{padding:10px 8px;border-bottom:1px solid rgba(255,255,255,.05);text-align:right;vertical-align:top}
    .section-head{background:linear-gradient(135deg,#3b82f6,#06b6d4);font-weight:700}
    .status-box,.result-box,.error-box,.qr-box{padding:14px;border-radius:14px;margin-top:14px;display:none}
    .status-box{background:rgba(59,130,246,.10);border:1px solid rgba(59,130,246,.22);color:#d9f1ff}
    .result-box{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.22);color:#dcfce7}
    .error-box{background:rgba(248,113,113,.10);border:1px solid rgba(248,113,113,.22);color:#fee2e2}
    .qr-box{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);text-align:center}
    .code{margin-top:10px;padding:16px;border-radius:14px;background:rgba(0,0,0,.22);font-size:28px;letter-spacing:4px;text-align:center;direction:ltr;font-weight:800}
    .qr-image{width:min(100%,320px);background:#fff;padding:10px;border-radius:16px}
    .buttons-line{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
    .heart{position:fixed;bottom:-20px;font-size:20px;animation:floatHearts 5s linear infinite;color:#7dd3fc;z-index:5;pointer-events:none}
    @keyframes floatHearts {0%{transform:translateY(0);opacity:1}100%{transform:translateY(-120vh);opacity:0}}
    @media (max-width:920px){.hero-grid,.button-grid,.api-grid,.cards-grid,.row{grid-template-columns:1fr 1fr}.topbar{flex-wrap:wrap}}
    @media (max-width:640px){.hero-grid,.button-grid,.api-grid,.cards-grid,.row{grid-template-columns:1fr}.brand-pill{width:100%;justify-content:center}.panel-head{flex-direction:column;align-items:flex-start}}
  </style>
</head>
<body>
  <div id="overlay" class="overlay"></div>
  <aside id="sidebar" class="sidebar"><div class="sidebar-inner">
    <div class="brand">
      <h3>${siteName}</h3>
      <button class="close-btn" id="closeSidebar">✕</button>
    </div>
    <div class="brand-badge">KnightBot MD • Freebot UI</div>
    <div class="side-card">
      <h4>Info</h4>
      <div class="side-list">
        <div class="side-item"><span>Battery</span><strong id="sideBattery">Loading...</strong></div>
        <div class="side-item"><span>Network</span><strong id="sideNetwork">Loading...</strong></div>
        <div class="side-item"><span>IP Address</span><strong id="sideIp">Loading...</strong></div>
        <div class="side-item"><span>Time</span><strong id="sideTime">--:--:--</strong></div>
        <div class="side-item"><span>Active Bot</span><strong id="sideActive">0</strong></div>
        <div class="side-item"><span>Linked Numbers</span><strong id="sideLinked">0</strong></div>
      </div>
    </div>
    <div class="side-card">
      <h4>Menu</h4>
      <div class="side-btns">
        <button class="side-btn" id="goHomeBtn">🏠 Home</button>
        <button class="side-btn" id="openSettingsBtn">⚙️ Settings</button>
        <button class="side-btn" id="openCommandsSideBtn">📦 Command Sections</button>
        <button class="side-btn" id="openPairSideBtn">🔗 Pair Code</button>
        <button class="side-btn" id="openQrSideBtn">📷 QR Code</button>
        <button class="side-btn" id="refreshDataSideBtn">🔄 Update Data</button>
      </div>
    </div>
  </div></aside>

  <main class="page">
    <div class="topbar">
      <button id="openSidebar" class="menu-btn">☰ Menu</button>
      <div class="brand-pill"><strong>${siteName}</strong><span>•</span><span>واجهة الربط المستقلة</span></div>
    </div>

    <section class="hero">
      <div class="hero-grid">
        <div>
          <h1>${siteName}</h1>
          <p>واجهة مستقلة مضافة داخل مشروع <strong>KnightBot MD</strong> بنفس فكرة صفحة <strong>Freebot</strong>، ومربوطة مباشرة مع البوت وواجهة الإعدادات وواجهات Pair/QR الحالية داخل المشروع مع دعم استرجاع الجلسات والإحصائيات الكاملة.</p>
          <div class="stats-row">
            <div class="stat"><div class="value" id="activeBots">0</div><div class="label">إجمالي البوتات</div></div>
            <div class="stat"><div class="value" id="onlineBotsHero">0</div><div class="label">المتصل الآن</div></div>
            <div class="stat"><div class="value" id="linkedNumbers">0</div><div class="label">الأرقام المربوطة</div></div>
            <div class="stat"><div class="value" id="totalUsers">0</div><div class="label">المستخدمون</div></div>
          </div>
        </div>
        <div class="hero-banner">
          <div class="banner-box">
            <div class="kicker">Standalone Linking Panel</div>
            <div class="title">${siteName}<br/>Multi Device WhatsApp Bot</div>
            <div class="sub">زر Pair Code يستخدم <code>/api/pairing</code>، وزر QR يستخدم <code>/api/qr</code>، وزر الإعدادات يفتح لوحة إعدادات الرقم داخل نفس المشروع.</div>
          </div>
        </div>
      </div>
    </section>

    <section class="button-grid">
      <button class="action-btn primary" id="pairBtn"><strong>PAIR CODE</strong><span>استخراج كود الربط</span></button>
      <button class="action-btn success" id="qrBtn"><strong>QR CODE</strong><span>ربط بالمسح</span></button>
      <button class="action-btn warn" id="settingsBtn"><strong>الإعدادات</strong><span>لوحة إعدادات الرقم</span></button>
      <button class="action-btn" id="apiInfoBtn"><strong>API INFO</strong><span>معلومات الربط</span></button>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div class="panel-title">مربوط مع البوت وواجهة الإعدادات</div>
        <div class="pill">Route: <span id="routeText">${basePath}</span></div>
      </div>
      <div class="api-grid">
        <div class="api-card"><small>Pairing Endpoint</small><code id="pairEndpoint">/api/pairing</code></div>
        <div class="api-card"><small>Settings URL</small><code id="settingsEndpoint">${basePath}/settings</code></div>
        <div class="api-card"><small>Website Base</small><code id="websiteEndpoint">/</code></div>
      </div>
      <div class="buttons-line">
        <button class="cmd-btn" id="openCommandsBtn">📜 عرض أقسام الأوامر</button>
        <button class="ghost-btn" id="refreshSummaryBtn">تحديث البيانات</button>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div class="panel-title">إحصائيات البوت والجلسات</div>
        <div class="pill">Live Stats</div>
      </div>
      <div class="api-grid">
        <div class="api-card"><small>البوتات المتصلة الآن</small><code id="onlineBots">0</code></div>
        <div class="api-card"><small>الجلسات المحفوظة</small><code id="storedSessions">0</code></div>
        <div class="api-card"><small>إجمالي ملفات الأوامر</small><code id="commandsCount">0</code></div>
        <div class="api-card"><small>الرسائل المستلمة</small><code id="incomingMessages">0</code></div>
        <div class="api-card"><small>مرات إعادة الاتصال</small><code id="reconnects">0</code></div>
        <div class="api-card"><small>مرات تشغيل الجلسات</small><code id="sessionsStarted">0</code></div>
      </div>
      <div class="api-grid" style="margin-top:12px">
        <div class="api-card"><small>رابط الموقع</small><code id="mainSiteUrl">/</code></div>
        <div class="api-card"><small>رابط الإعدادات</small><code id="settingsSiteUrl">${basePath}/settings</code></div>
        <div class="api-card"><small>API الربط</small><code id="pairingApiUrl">/api/pairing</code></div>
      </div>
    </section>

    <section class="desc-card">
      <h2>عن ${siteName}</h2>
      <p>هذه الواجهة الجديدة أُضيفت داخل مشروعك لتكون صفحة مستقلة بالرابط الخاص بها، بنفس روح تصميم صفحة Freebot: خلفية غامقة، زجاجية، أزرار Pair / QR، قسم أوامر، وقسم تعليقات. كما أنها تستخدم واجهات الربط الفعلية الموجودة في مشروعك بدل أن تكون مجرد تصميم ثابت.</p>
    </section>

    <section class="components">
      <h2>مكونات الواجهة</h2>
      <p>كل عنصر هنا مربوط فعليًا بما هو موجود في المشروع: الربط، QR، الإعدادات، الإحصائيات، والجلسات المحفوظة التي يمكن استعادتها تلقائياً بعد إعادة التشغيل.</p>
      <div class="cards-grid">
        <div class="component-card"><div class="avatar">🔗</div><h4>Pair API</h4><small>استخراج الأكواد عبر API المشروع</small></div>
        <div class="component-card"><div class="avatar">📷</div><h4>QR Bridge</h4><small>جلب QR مباشرة من المشروع</small></div>
        <div class="component-card"><div class="avatar">⚙️</div><h4>Settings Panel</h4><small>فتح صفحة الإعدادات بنفس المشروع</small></div>
        <div class="component-card"><div class="avatar">💬</div><h4>Comments</h4><small>تعليقات محفوظة داخل ملفات المشروع</small></div>
        <div class="component-card"><div class="avatar">📊</div><h4 id="commandSectionsCount">0</h4><small>أقسام الأوامر</small></div>
        <div class="component-card"><div class="avatar">🧠</div><h4 id="commandEntriesCount">0</h4><small>إجمالي عناصر الأوامر</small></div>
        <div class="component-card"><div class="avatar">📸</div><h4 id="statusEvents">0</h4><small>الحالات المحفوظة</small></div>
        <div class="component-card"><div class="avatar">😍</div><h4 id="statusReactions">0</h4><small>تفاعلات الحالة</small></div>
      </div>
    </section>

    <section class="comment-box">
      <h3>إضافة تعليق جديد</h3>
      <div class="row">
        <input id="name" class="input" placeholder="الاسم" />
        <input id="commentPhone" class="input" placeholder="رقم اختياري للتواصل" />
      </div>
      <textarea id="comment" placeholder="اكتب تعليقك هنا"></textarea>
      <div class="buttons-line">
        <button class="comment-btn" id="submitCommentBtn">إرسال التعليق</button>
        <button class="ghost-btn" id="showAllCommentsBtn">إظهار كل التعليقات</button>
      </div>
      <div id="commentError" class="error-box"></div>
    </section>

    <section class="comments-list">
      <h3>آخر التعليقات</h3>
      <div id="commentsList"></div>
    </section>

    <footer>© 2026 ${siteName} — KnightBot MD</footer>
  </main>

  <div id="commandsPopup" class="popup-overlay"><div class="popup-content"><div class="popup-header"><h2>📜 أقسام أوامر KnightBot MD</h2><button class="close-btn" data-close-popup>✕</button></div><div class="popup-body"><table><thead><tr><th>الأمر</th><th>مثال</th><th>الوصف</th></tr></thead><tbody>${tableRows}</tbody></table></div></div></div>

  <div id="pairPopup" class="popup-overlay"><div class="popup-content"><div class="popup-header"><h2>🔗 Pair Code</h2><button class="close-btn" data-close-popup>✕</button></div><div class="popup-body">
    <input id="pairNumber" class="input" inputmode="numeric" placeholder="مثال: 9677XXXXXXX" />
    <div class="buttons-line"><button class="primary-btn" id="submitPairBtn">استخراج كود الربط</button><button class="ghost-btn" id="copyCodeBtn" style="display:none">نسخ الكود</button></div>
    <div id="pairStatus" class="status-box"></div>
    <div id="pairResult" class="result-box"><div>✅ تم إنشاء الكود بنجاح</div><div id="pairNumberResult"></div><div id="pairCodeResult" class="code"></div></div>
    <div id="pairError" class="error-box"></div>
  </div></div></div>

  <div id="qrPopup" class="popup-overlay"><div class="popup-content"><div class="popup-header"><h2>📷 QR Code</h2><button class="close-btn" data-close-popup>✕</button></div><div class="popup-body">
    <div class="qr-box" style="display:block">
      <p style="margin-top:0;color:var(--muted)">امسح هذا الكود من واتساب > الأجهزة المرتبطة > ربط جهاز</p>
      <img id="qrImage" class="qr-image" alt="QR Code" />
      <div class="buttons-line" style="justify-content:center"><button class="primary-btn" id="refreshQrBtn">تحديث QR</button></div>
      <div id="qrError" class="error-box"></div>
    </div>
  </div></div></div>

<script>
const CONFIG = ${config};
let comments = [];
let showingAll = false;
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

function openSidebar(){ $('#sidebar').style.width='320px'; $('#overlay').classList.add('visible'); }
function closeSidebar(){ $('#sidebar').style.width='0'; $('#overlay').classList.remove('visible'); }
function openPopup(id){ $(id).classList.add('show'); }
function closePopups(){ $$('.popup-overlay').forEach(el=>el.classList.remove('show')); }
function showBox(id, text){ const el=$(id); el.textContent=text; el.style.display='block'; }
function hideBox(id){ const el=$(id); el.style.display='none'; el.textContent=''; }
function setTextIfExists(id, value){ const el=$(id); if(el) el.textContent = value; }
function escapeHtml(value){ return String(value||'').replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }

async function loadSummary(){
  try {
    const res = await fetch(CONFIG.summaryUrl, { cache:'no-store' });
    const data = await res.json();
    setTextIfExists('#activeBots', data.activeBots ?? 0);
    setTextIfExists('#onlineBotsHero', data.onlineBots ?? data.activeBots ?? 0);
    setTextIfExists('#linkedNumbers', data.totalLinkedNumbers ?? 0);
    setTextIfExists('#totalUsers', data.totalUsers ?? 0);
    setTextIfExists('#sideActive', data.onlineBots ?? data.activeBots ?? 0);
    setTextIfExists('#sideLinked', data.totalLinkedNumbers ?? 0);
    setTextIfExists('#pairEndpoint', data.pairing?.endpoint || '/api/pairing');
    setTextIfExists('#settingsEndpoint', data.settingsUrl || CONFIG.settingsUrl);
    setTextIfExists('#websiteEndpoint', data.pairing?.website || location.origin);
    setTextIfExists('#routeText', data.route || CONFIG.basePath);
    setTextIfExists('#onlineBots', data.onlineBots ?? data.activeBots ?? 0);
    setTextIfExists('#storedSessions', data.storedSessions ?? 0);
    setTextIfExists('#commandsCount', data.commandsCount ?? 0);
    setTextIfExists('#incomingMessages', data.analytics?.totalIncomingMessages ?? 0);
    setTextIfExists('#reconnects', data.analytics?.totalReconnects ?? 0);
    setTextIfExists('#sessionsStarted', data.analytics?.totalSessionsStarted ?? 0);
    setTextIfExists('#statusEvents', data.analytics?.totalStatusEvents ?? 0);
    setTextIfExists('#statusReactions', data.analytics?.totalStatusReactions ?? 0);
    setTextIfExists('#commandSectionsCount', data.commandSectionsCount ?? 0);
    setTextIfExists('#commandEntriesCount', data.commandEntriesCount ?? 0);
    setTextIfExists('#mainSiteUrl', data.routes?.main || data.pairing?.website || location.origin);
    setTextIfExists('#settingsSiteUrl', data.routes?.settings || data.settingsUrl || CONFIG.settingsUrl);
    setTextIfExists('#pairingApiUrl', data.routes?.pairing || data.pairing?.endpoint || '/api/pairing');
  } catch (_) {
    setTextIfExists('#sideActive', 'Unavailable');
  }
}

function tickClock(){ try { $('#sideTime').textContent = new Date().toLocaleTimeString('ar-EG'); } catch(_){} }

async function loadDeviceInfo(){
  try {
    if (navigator.getBattery) {
      const battery = await navigator.getBattery();
      setTextIfExists('#sideBattery', Math.round((battery.level || 0) * 100) + '%');
    } else {
      setTextIfExists('#sideBattery', 'Not Supported');
    }
  } catch (_) {
    setTextIfExists('#sideBattery', 'Unavailable');
  }

  try {
    const network = navigator.connection?.effectiveType || navigator.connection?.type || 'Unknown';
    setTextIfExists('#sideNetwork', network);
  } catch (_) {
    setTextIfExists('#sideNetwork', 'Unknown');
  }

  try {
    const res = await fetch('https://api.ipify.org?format=json');
    const data = await res.json();
    setTextIfExists('#sideIp', data.ip || 'Unavailable');
  } catch (_) {
    setTextIfExists('#sideIp', 'Unavailable');
  }
}

async function submitPairCode(){
  hideBox('#pairStatus'); hideBox('#pairError'); $('#pairResult').style.display='none';
  const number = String($('#pairNumber').value || '').trim();
  if(!number){ return showBox('#pairError','أدخل رقم واتساب أولاً'); }
  showBox('#pairStatus','جاري إنشاء كود الربط، انتظر قليلاً...');
  $('#submitPairBtn').disabled = true;
  try{
    const res = await fetch(CONFIG.pairApiUrl, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ phone:number }) });
    const data = await res.json();
    if(!res.ok || !data.success) throw new Error(data.error || 'فشل إنشاء الكود');
    hideBox('#pairStatus');
    $('#pairNumberResult').textContent = '📱 الرقم: ' + (data.phone || data.num || number);
    $('#pairCodeResult').textContent = data.code || '';
    $('#pairResult').style.display = 'block';
    $('#copyCodeBtn').style.display = 'inline-block';
    loadSummary();
  }catch(error){
    hideBox('#pairStatus');
    showBox('#pairError', error.message || 'حدث خطأ أثناء استخراج الكود');
  }finally{
    $('#submitPairBtn').disabled = false;
  }
}

async function copyPairCode(){
  const code = String($('#pairCodeResult').textContent || '').trim();
  if(!code) return;
  try{ await navigator.clipboard.writeText(code); $('#copyCodeBtn').textContent='تم النسخ'; setTimeout(()=>$('#copyCodeBtn').textContent='نسخ الكود', 1500); }catch(_){ $('#copyCodeBtn').textContent='انسخ يدويًا'; }
}

function loadQr(){
  hideBox('#qrError');
  const img = $('#qrImage');
  img.onload = () => { $('#qrError').style.display='none'; };
  img.onerror = () => { showBox('#qrError','تعذر تحميل QR حالياً، أعد المحاولة بعد لحظات'); };
  img.src = CONFIG.qrUrl + '?refresh=1&t=' + Date.now();
}

async function loadComments(){
  try{
    const res = await fetch(CONFIG.commentsUrl, { cache:'no-store' });
    const data = await res.json();
    comments = Array.isArray(data.comments) ? data.comments : [];
    renderComments();
  }catch(_){ $('#commentsList').innerHTML = '<div class="comment">تعذر تحميل التعليقات حالياً.</div>'; }
}

function renderComments(){
  const list = $('#commentsList');
  const view = showingAll ? comments : comments.slice(0, 10);
  if(!view.length){ list.innerHTML = '<div class="comment">لا توجد تعليقات بعد.</div>'; return; }
  list.innerHTML = view.map((c) => {
    const replies = Array.isArray(c.replies)
      ? c.replies.map((reply) => '<div style="margin-top:8px;color:#bfe8ff">↳ ' + escapeHtml(reply) + '</div>').join('')
      : '';
    const reacts = Array.isArray(c.reacts) ? c.reacts : [0,0,0,0,0];
    return ''
      + '<div class="comment">'
      + (c.pinned ? '<div class="pinned">📌</div>' : '')
      + '<strong>' + escapeHtml(c.name) + '</strong><br>'
      + '<small>' + escapeHtml(c.date || '') + ' ' + escapeHtml(c.time || '') + (c.phone ? ' • ' + escapeHtml(c.phone) : '') + '</small>'
      + '<p>' + escapeHtml(c.comment) + '</p>'
      + '<div class="reacts">'
      + '<span class="react-chip" onclick="reactComment(\'' + c.id + '\',0)">❤️ ' + (reacts[0] || 0) + '</span>'
      + '<span class="react-chip" onclick="reactComment(\'' + c.id + '\',1)">😍 ' + (reacts[1] || 0) + '</span>'
      + '<span class="react-chip" onclick="reactComment(\'' + c.id + '\',2)">😂 ' + (reacts[2] || 0) + '</span>'
      + '<span class="react-chip" onclick="reactComment(\'' + c.id + '\',3)">😮 ' + (reacts[3] || 0) + '</span>'
      + '<span class="react-chip" onclick="reactComment(\'' + c.id + '\',4)">😢 ' + (reacts[4] || 0) + '</span>'
      + '</div>'
      + '<div class="meta-actions">'
      + '<span class="admin-link" onclick="replyComment(\'' + c.id + '\')">Reply</span>'
      + '<span class="admin-link" onclick="pinComment(\'' + c.id + '\', ' + (c.pinned ? 'true' : 'false') + ')">Pin</span>'
      + '</div>'
      + replies
      + '</div>';
  }).join('');
}

async function submitComment(){
  hideBox('#commentError');
  const name = String($('#name').value || '').trim();
  const phone = String($('#commentPhone').value || '').trim();
  const comment = String($('#comment').value || '').trim();
  if(!name || !comment){ return showBox('#commentError','أدخل الاسم والتعليق أولاً'); }
  try{
    const res = await fetch(CONFIG.commentPostUrl, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name, phone, comment }) });
    const data = await res.json();
    if(!res.ok || !data.success) throw new Error(data.error || 'فشل حفظ التعليق');
    $('#name').value=''; $('#commentPhone').value=''; $('#comment').value='';
    comments = Array.isArray(data.comments) ? data.comments : comments;
    showingAll = false;
    renderComments();
  }catch(error){ showBox('#commentError', error.message || 'تعذر إرسال التعليق'); }
}

async function reactComment(id, index){
  const key = 'linking-reacted-comments';
  const reacted = JSON.parse(localStorage.getItem(key) || '[]');
  if(reacted.includes(id)) return alert('لقد تفاعلت مع هذا التعليق مسبقاً');
  const res = await fetch(CONFIG.reactUrl + '/' + encodeURIComponent(id), { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ index }) });
  const data = await res.json();
  if(!res.ok || !data.success) return alert(data.error || 'تعذر التفاعل');
  reacted.push(id); localStorage.setItem(key, JSON.stringify(reacted));
  comments = Array.isArray(data.comments) ? data.comments : comments; renderComments();
}

async function replyComment(id){
  const password = prompt('كلمة مرور الإدارة');
  if(!password) return;
  const reply = prompt('الرد');
  if(!reply) return;
  const res = await fetch(CONFIG.replyUrl + '/' + encodeURIComponent(id), { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ password, reply }) });
  const data = await res.json();
  if(!res.ok || !data.success) return alert(data.error || 'تعذر إضافة الرد');
  comments = Array.isArray(data.comments) ? data.comments : comments; renderComments();
}

async function pinComment(id, current){
  const password = prompt('كلمة مرور الإدارة');
  if(!password) return;
  const res = await fetch(CONFIG.pinUrl + '/' + encodeURIComponent(id), { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ password, pinned: !current }) });
  const data = await res.json();
  if(!res.ok || !data.success) return alert(data.error || 'تعذر تثبيت التعليق');
  comments = Array.isArray(data.comments) ? data.comments : comments; renderComments();
}

function spawnHeart(){ const heart=document.createElement('div'); heart.className='heart'; heart.style.left=Math.random()*window.innerWidth+'px'; heart.textContent='🩵'; document.body.appendChild(heart); setTimeout(()=>heart.remove(), 5000); }

$('#openSidebar').addEventListener('click', openSidebar);
$('#closeSidebar').addEventListener('click', closeSidebar);
$('#overlay').addEventListener('click', closeSidebar);
$$('[data-close-popup]').forEach(btn => btn.addEventListener('click', closePopups));
$('#pairBtn').addEventListener('click', ()=>openPopup('#pairPopup'));
$('#qrBtn').addEventListener('click', ()=>{ openPopup('#qrPopup'); loadQr(); });
$('#settingsBtn').addEventListener('click', ()=>location.href = CONFIG.settingsUrl);
$('#apiInfoBtn').addEventListener('click', ()=>window.open(CONFIG.summaryUrl,'_blank'));
$('#openSettingsBtn').addEventListener('click', ()=>location.href = CONFIG.settingsUrl);
$('#goHomeBtn').addEventListener('click', ()=>location.href = CONFIG.basePath);
$('#openCommandsBtn').addEventListener('click', ()=>openPopup('#commandsPopup'));
$('#openCommandsSideBtn').addEventListener('click', ()=>openPopup('#commandsPopup'));
$('#openPairSideBtn').addEventListener('click', ()=>openPopup('#pairPopup'));
$('#openQrSideBtn').addEventListener('click', ()=>{ openPopup('#qrPopup'); loadQr(); });
$('#submitPairBtn').addEventListener('click', submitPairCode);
$('#copyCodeBtn').addEventListener('click', copyPairCode);
$('#refreshQrBtn').addEventListener('click', loadQr);
$('#submitCommentBtn').addEventListener('click', submitComment);
$('#showAllCommentsBtn').addEventListener('click', ()=>{ showingAll = !showingAll; $('#showAllCommentsBtn').textContent = showingAll ? 'إظهار آخر 10' : 'إظهار كل التعليقات'; renderComments(); });
$('#refreshSummaryBtn').addEventListener('click', loadSummary);
$('#refreshDataSideBtn').addEventListener('click', ()=>{ loadSummary(); loadDeviceInfo(); });
$('#pairNumber').addEventListener('keydown', (event)=>{ if(event.key==='Enter') submitPairCode(); });

loadSummary(); loadComments(); loadDeviceInfo(); tickClock(); setInterval(tickClock, 1000); setInterval(spawnHeart, 650);
</script>
</body>
</html>`;
  }

  aliases.forEach((basePath) => {
    app.get(basePath, (req, res) => {
      return res.sendFile(path.join(PUBLIC_DIR, 'pair.html'));
    });

    app.get(`${basePath}/pair`, (req, res) => {
      return res.sendFile(path.join(PUBLIC_DIR, 'pair.html'));
    });

    app.get(`${basePath}/settings`, (req, res) => {
      return res.sendFile(path.join(PUBLIC_DIR, 'settings.html'));
    });
  });

  app.get('/count', (req, res) => {
    const linkedPhones = Array.isArray(getAllLinkedPhones()) ? getAllLinkedPhones() : [];
    res.json({ count: linkedPhones.length });
  });

  app.get('/api/linking-site/summary', (req, res) => {
    res.json(getSummaryPayload());
  });

  app.get('/api/linking-site/comments', (req, res) => {
    res.json({ success: true, comments: sortComments(readComments()) });
  });

  app.post('/api/linking-site/comment', (req, res) => {
    try {
      const name = String(req.body?.name || '').trim();
      const phone = String(req.body?.phone || '').trim();
      const comment = String(req.body?.comment || '').trim();
      if (!name || !comment) {
        return res.status(400).json({ success: false, error: 'الاسم والتعليق مطلوبان' });
      }
      if (!/^[\p{L}\p{N}\s._-]{2,40}$/u.test(name)) {
        return res.status(400).json({ success: false, error: 'الاسم غير صالح' });
      }
      if (comment.length < 2 || comment.length > 500) {
        return res.status(400).json({ success: false, error: 'التعليق يجب أن يكون بين 2 و500 حرف' });
      }
      const now = new Date();
      const dt = formatDateTime(now);
      const comments = readComments();
      comments.unshift({
        id: crypto.randomUUID(),
        name,
        phone: normalizePhone(phone || ''),
        comment,
        reacts: [0, 0, 0, 0, 0],
        replies: [],
        pinned: false,
        date: dt.date,
        time: dt.time,
        createdAt: now.toISOString()
      });
      writeComments(comments);
      return res.json({ success: true, comments: sortComments(comments) });
    } catch (error) {
      return res.status(500).json({ success: false, error: error.message || 'فشل حفظ التعليق' });
    }
  });

  app.put('/api/linking-site/react/:id', (req, res) => {
    try {
      const index = Number(req.body?.index);
      if (![0, 1, 2, 3, 4].includes(index)) {
        return res.status(400).json({ success: false, error: 'نوع التفاعل غير صالح' });
      }
      const comments = readComments();
      const target = comments.find((item) => item.id === String(req.params?.id || ''));
      if (!target) {
        return res.status(404).json({ success: false, error: 'التعليق غير موجود' });
      }
      if (!Array.isArray(target.reacts)) target.reacts = [0, 0, 0, 0, 0];
      target.reacts[index] = Number(target.reacts[index] || 0) + 1;
      writeComments(comments);
      return res.json({ success: true, comments: sortComments(comments) });
    } catch (error) {
      return res.status(500).json({ success: false, error: error.message || 'فشل التفاعل' });
    }
  });

  app.put('/api/linking-site/reply/:id', (req, res) => {
    try {
      if (!isAdminAuthorized(req)) {
        return res.status(401).json({ success: false, error: 'كلمة مرور الإدارة غير صحيحة' });
      }
      const reply = String(req.body?.reply || '').trim();
      if (!reply) {
        return res.status(400).json({ success: false, error: 'الرد مطلوب' });
      }
      const comments = readComments();
      const target = comments.find((item) => item.id === String(req.params?.id || ''));
      if (!target) {
        return res.status(404).json({ success: false, error: 'التعليق غير موجود' });
      }
      if (!Array.isArray(target.replies)) target.replies = [];
      target.replies.push(reply);
      writeComments(comments);
      return res.json({ success: true, comments: sortComments(comments) });
    } catch (error) {
      return res.status(500).json({ success: false, error: error.message || 'فشل إضافة الرد' });
    }
  });

  app.put('/api/linking-site/pin/:id', (req, res) => {
    try {
      if (!isAdminAuthorized(req)) {
        return res.status(401).json({ success: false, error: 'كلمة مرور الإدارة غير صحيحة' });
      }
      const comments = readComments();
      const target = comments.find((item) => item.id === String(req.params?.id || ''));
      if (!target) {
        return res.status(404).json({ success: false, error: 'التعليق غير موجود' });
      }
      target.pinned = req.body?.pinned === true;
      writeComments(comments);
      return res.json({ success: true, comments: sortComments(comments) });
    } catch (error) {
      return res.status(500).json({ success: false, error: error.message || 'فشل تثبيت التعليق' });
    }
  });
}

module.exports = { attachLinkingSiteRoutes };
