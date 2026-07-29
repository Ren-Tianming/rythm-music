import { type DragEvent, type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type Analysis,
  type AuthResponse,
  type BrowserSession,
  type Founder,
  type Generation,
  type User,
  type Work
} from "./api";

type Locale = "zh" | "ja" | "en";
type Page = "studio" | "analyze" | "generate" | "works" | "history" | "founder" | "account";
type Dictionary = typeof copy.zh;
const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY ?? "";

const copy = {
  zh: {
    signIn: "登录", signUp: "注册", email: "邮箱", password: "密码", username: "用户名", start: "开始创作",
    heroTag: "AI 音乐分析与生成工作室", heroTitleA: "听见结构，", heroTitleB: "创造下一段声音。",
    heroBody: "上传歌曲，查看 BPM、调性、波形、频谱、曲风与 AI 解读；也可以从提示词生成音乐草稿并发布作品。",
    analyzeNow: "立即分析", viewWorks: "浏览作品", features: "核心能力", featureA: "精确分析", featureABody: "一次上传获得节拍、调性、响度、波形与频谱。",
    featureB: "曲风神经网络", featureBBody: "预留你原有的 Tonnetz + DNN 模型推理接口。", featureC: "音乐生成", featureCBody: "Key 接入前使用本地演示引擎，之后可切换外部服务。",
    authTitle: "进入 RyThM 工作室", authHint: "第一版 MVP · 安全 Cookie 会话", noAccount: "创建新账户", haveAccount: "返回登录", working: "处理中…",
    studio: "工作台", analyze: "乐曲分析", generate: "乐曲生成", works: "作品广场", history: "分析历史", founder: "RyThM 音乐", account: "账户安全", logout: "退出",
    welcome: "欢迎回来", welcomeBody: "从音频数据到音乐草稿，所有创作流程集中在一个工作台。", newAnalysis: "上传新歌曲", newGeneration: "生成音乐",
    balance: "积分余额", analyses: "分析次数", generations: "生成草稿", latestActivity: "最近活动", noActivity: "还没有数据，先上传一首歌或生成一段音乐。",
    analysisLab: "分析实验室", analysisBody: "支持 MP3、WAV、FLAC、M4A；最大 50 MB / 10 分钟。", drop: "拖放音频文件", browse: "或点击选择文件", run: "开始分析", analyzing: "正在提取节拍、调性、曲风与频谱…",
    bpm: "BPM", key: "调性", genre: "曲风", loudness: "响度", duration: "时长", waveform: "歌曲波形", spectrogram: "歌曲频谱", aiSummary: "歌曲分析", lyrics: "歌词提取", download: "下载 PDF 报告", notConfigured: "尚未配置", modelMissing: "需要加入原模型权重", modelError: "模型加载或推理失败", lyricsMissing: "需要配置转写 API Key",
    generationLab: "音乐生成实验室", generationBody: "描述风格、情绪、乐器和场景。当前 Demo 引擎生成短音频，之后可直接切换外部 API。", titleOptional: "标题（可选）", prompt: "音乐提示词", promptExample: "例如：夜晚东京，高速公路，紫色霓虹，120 BPM，合成器浪潮与深沉鼓组", instrumental: "纯音乐", seconds: "秒", create: "生成草稿", demoBadge: "DEMO 引擎 · 0 PT", myGenerations: "我的生成草稿", noGenerations: "尚未生成音乐。", publish: "发布作品", description: "作品说明", cover: "封面色彩", publishNow: "确认发布", published: "作品已发布。",
    community: "作品广场", communityBody: "试听其他创作者发布的作品。", noWorks: "还没有公开作品。", like: "喜欢",
    historyTitle: "分析历史", historyBody: "查看过去的分析结果与报告。", noHistory: "还没有分析记录。", success: "完成", failed: "失败",
    founderTag: "FOUNDER / PRODUCER", founderTitle: "创始人 RyThM 音乐", founderFallback: "音乐制作人与软件工程师，探索机器精度与人类节奏的交界。", founderWorks: "创始人作品", founderEmpty: "创始人音乐将陆续发布到这里。",
    requestFailed: "请求失败，请稍后重试。", registerBonus: "Argon2id · 邮箱激活 · 可撤销 Session", dailyBonus: "今日登录奖励", publicHome: "首页", durationMinute: "分", durationSecond: "秒",
    humanCheck: "请完成人机验证", verificationSent: "请检查邮箱并完成激活后登录。", securityTitle: "账户与设备", securityBody: "查看当前登录设备，并立即撤销任何服务端 Session。", devices: "登录设备", currentDevice: "当前设备", revoke: "立即撤销", revokeAll: "退出所有设备", lastSeen: "最近活动", unknownDevice: "未知设备"
  },
  ja: {
    signIn: "ログイン", signUp: "新規登録", email: "メール", password: "パスワード", username: "ユーザー名", start: "制作を始める",
    heroTag: "AI 音楽解析・生成スタジオ", heroTitleA: "音の構造を捉え、", heroTitleB: "次のサウンドを創る。",
    heroBody: "楽曲をアップロードして BPM、キー、波形、スペクトログラム、ジャンル、AI 解説を確認。プロンプトから音楽案を生成し、作品として公開できます。",
    analyzeNow: "今すぐ解析", viewWorks: "作品を見る", features: "主な機能", featureA: "精密な解析", featureABody: "一度のアップロードでテンポ、キー、音量、波形、スペクトルを取得。",
    featureB: "ジャンル DNN", featureBBody: "既存の Tonnetz + DNN モデルを接続できる推論口を用意。", featureC: "音楽生成", featureCBody: "Key 接続前はローカル Demo、接続後は外部サービスへ切替可能。",
    authTitle: "RyThM スタジオへ", authHint: "初版 MVP · セキュアCookieセッション", noAccount: "アカウントを作成", haveAccount: "ログインへ戻る", working: "処理中…",
    studio: "スタジオ", analyze: "楽曲解析", generate: "楽曲生成", works: "作品広場", history: "解析履歴", founder: "RyThM Music", account: "アカウント保護", logout: "ログアウト",
    welcome: "おかえりなさい", welcomeBody: "音声データから音楽草稿まで、制作フローを一つのスタジオに。", newAnalysis: "楽曲をアップロード", newGeneration: "音楽を生成",
    balance: "ポイント残高", analyses: "解析回数", generations: "生成草稿", latestActivity: "最近のアクティビティ", noActivity: "データがありません。楽曲解析または音楽生成から始めましょう。",
    analysisLab: "解析ラボ", analysisBody: "MP3 / WAV / FLAC / M4A、最大 50 MB・10 分。", drop: "音源をドロップ", browse: "またはクリックして選択", run: "解析開始", analyzing: "テンポ、キー、ジャンル、スペクトルを抽出中…",
    bpm: "BPM", key: "キー", genre: "ジャンル", loudness: "ラウドネス", duration: "長さ", waveform: "波形", spectrogram: "スペクトログラム", aiSummary: "楽曲分析", lyrics: "歌詞抽出", download: "PDF レポート", notConfigured: "未設定", modelMissing: "元モデルの重みが必要です", modelError: "モデルの読み込みまたは推論に失敗しました", lyricsMissing: "文字起こし API Key が必要です",
    generationLab: "音楽生成ラボ", generationBody: "スタイル、感情、楽器、場面を記述してください。現在は短い Demo 音源を生成し、後から外部 API に切替できます。", titleOptional: "タイトル（任意）", prompt: "音楽プロンプト", promptExample: "例：夜の東京、高速道路、紫のネオン、120 BPM、シンセウェーブと重いドラム", instrumental: "インストゥルメンタル", seconds: "秒", create: "草稿を生成", demoBadge: "DEMO エンジン · 0 PT", myGenerations: "生成した草稿", noGenerations: "生成した音楽はありません。", publish: "作品を公開", description: "作品説明", cover: "カバーカラー", publishNow: "公開する", published: "作品を公開しました。",
    community: "作品広場", communityBody: "他のクリエイターが公開した作品を試聴できます。", noWorks: "公開作品はまだありません。", like: "Like",
    historyTitle: "解析履歴", historyBody: "過去の解析結果とレポートを確認。", noHistory: "解析履歴はありません。", success: "完了", failed: "失敗",
    founderTag: "FOUNDER / PRODUCER", founderTitle: "創業者 RyThM の音楽", founderFallback: "機械の精度と人間のリズムの境界を探る、音楽プロデューサー兼ソフトウェアエンジニア。", founderWorks: "Founder Tracks", founderEmpty: "Founder の楽曲は順次公開予定です。",
    requestFailed: "処理に失敗しました。しばらくしてから再試行してください。", registerBonus: "Argon2id・メール確認・取消可能Session", dailyBonus: "本日のログインボーナス", publicHome: "ホーム", durationMinute: "分", durationSecond: "秒",
    humanCheck: "人間確認を完了してください", verificationSent: "確認メールから有効化した後、ログインしてください。", securityTitle: "アカウントと端末", securityBody: "ログイン中の端末を確認し、サーバーSessionを即時失効できます。", devices: "ログイン端末", currentDevice: "現在の端末", revoke: "今すぐ失効", revokeAll: "全端末からログアウト", lastSeen: "最終利用", unknownDevice: "不明な端末"
  },
  en: {
    signIn: "Sign in", signUp: "Create account", email: "Email", password: "Password", username: "Username", start: "Start creating",
    heroTag: "AI MUSIC ANALYSIS & GENERATION STUDIO", heroTitleA: "See the structure.", heroTitleB: "Create the next sound.",
    heroBody: "Upload music for BPM, key, waveform, spectrum, genre and AI insight. Turn prompts into drafts and publish your work.",
    analyzeNow: "Analyze now", viewWorks: "Explore works", features: "Core capabilities", featureA: "Precise analysis", featureABody: "Tempo, key, loudness, waveform and spectrum from one upload.",
    featureB: "Genre neural network", featureBBody: "Inference adapter for your existing Tonnetz + DNN model.", featureC: "Music generation", featureCBody: "Local demo before keys; external provider when connected.",
    authTitle: "Enter RyThM Studio", authHint: "MVP v0.1 · Secure cookie session", noAccount: "Create a new account", haveAccount: "Back to sign in", working: "Working…",
    studio: "Studio", analyze: "Analyze", generate: "Generate", works: "Community", history: "History", founder: "RyThM Music", account: "Account security", logout: "Log out",
    welcome: "Welcome back", welcomeBody: "From audio data to music drafts, all in one creative workspace.", newAnalysis: "Upload a track", newGeneration: "Generate music",
    balance: "Point balance", analyses: "Analyses", generations: "Drafts", latestActivity: "Latest activity", noActivity: "No data yet. Analyze a track or generate a draft.",
    analysisLab: "Analysis lab", analysisBody: "MP3, WAV, FLAC or M4A · Up to 50 MB / 10 minutes.", drop: "Drop an audio file", browse: "or click to browse", run: "Run analysis", analyzing: "Extracting tempo, key, genre and spectrum…",
    bpm: "BPM", key: "Key", genre: "Genre", loudness: "Loudness", duration: "Duration", waveform: "Waveform", spectrogram: "Spectrogram", aiSummary: "Music analysis", lyrics: "Lyrics", download: "Download PDF", notConfigured: "Not configured", modelMissing: "Original model weights required", modelError: "Model loading or inference failed", lyricsMissing: "Transcription API key required",
    generationLab: "Music generation lab", generationBody: "Describe style, mood, instruments and scene. The current demo makes a short preview; an external API can replace it later.", titleOptional: "Title (optional)", prompt: "Music prompt", promptExample: "Example: Tokyo highway at night, violet neon, 120 BPM, synthwave and deep drums", instrumental: "Instrumental", seconds: "sec", create: "Generate draft", demoBadge: "DEMO ENGINE · 0 PT", myGenerations: "My drafts", noGenerations: "No generated music yet.", publish: "Publish work", description: "Description", cover: "Cover color", publishNow: "Publish", published: "Your work is now public.",
    community: "Community works", communityBody: "Listen to work published by other creators.", noWorks: "No public works yet.", like: "Like",
    historyTitle: "Analysis history", historyBody: "Review past results and reports.", noHistory: "No analysis history yet.", success: "Success", failed: "Failed",
    founderTag: "FOUNDER / PRODUCER", founderTitle: "Music by founder RyThM", founderFallback: "A music producer and software engineer exploring the border between machine precision and human rhythm.", founderWorks: "Founder tracks", founderEmpty: "Founder tracks will appear here as they are released.",
    requestFailed: "Request failed. Please try again.", registerBonus: "Argon2id · email verified · revocable session", dailyBonus: "Daily login bonus", publicHome: "Home", durationMinute: " min ", durationSecond: " sec",
    humanCheck: "Complete the human check", verificationSent: "Check your email and activate the account before signing in.", securityTitle: "Account and devices", securityBody: "Review signed-in devices and revoke any server session immediately.", devices: "Signed-in devices", currentDevice: "Current device", revoke: "Revoke now", revokeAll: "Log out all devices", lastSeen: "Last active", unknownDevice: "Unknown device"
  }
} as const;

function numericValue(value: number | string | null): number | null {
  if (value === null || (typeof value === "string" && value.trim() === "")) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatDuration(value: number | string | null, t: Dictionary): string {
  const numeric = numericValue(value);
  if (numeric === null) return "—";
  const totalSeconds = Math.max(0, Math.round(numeric));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}${t.durationMinute}${seconds}${t.durationSecond}`;
}

function formatBpm(value: number | string | null): string | number {
  const numeric = numericValue(value);
  return numeric === null ? "—" : Math.round(numeric);
}

function formatMusicalKey(value: string | null): string {
  if (!value) return "—";
  return value
    .replace(/\s*(メジャー|長調)$/u, " major")
    .replace(/\s*(マイナー|短調)$/u, " minor");
}

const navItems: Array<{ page: Page; mark: string }> = [
  { page: "studio", mark: "◈" }, { page: "analyze", mark: "⌁" }, { page: "generate", mark: "✦" },
  { page: "works", mark: "◎" }, { page: "history", mark: "≡" }, { page: "founder", mark: "R" },
  { page: "account", mark: "◇" }
];

function initialLocale(): Locale {
  const stored = localStorage.getItem("rythm_locale");
  if (stored === "zh" || stored === "ja" || stored === "en") return stored;
  return navigator.language.startsWith("ja") ? "ja" : navigator.language.startsWith("zh") ? "zh" : "en";
}

export function App() {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const [user, setUser] = useState<User | null>(null);
  const [page, setPage] = useState<Page>("studio");
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const t = copy[locale] as Dictionary;

  useEffect(() => {
    const hash = new URLSearchParams(window.location.hash.slice(1));
    const verificationToken = hash.get("verify");
    if (verificationToken) {
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    }
    const verify = verificationToken
      ? api.verifyEmail(verificationToken).then((result) => {
          setNotice(result.message);
        })
      : Promise.resolve();
    verify
      .then(() => api.me())
      .then(setUser)
      .catch((reason) => {
        setUser(null);
        if (verificationToken && reason instanceof Error && !reason.message.includes("ログイン")) {
          setNotice(reason.message);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  function setLocale(next: Locale) {
    setLocaleState(next);
    localStorage.setItem("rythm_locale", next);
  }

  function signedIn(result: AuthResponse) {
    setUser(result.user);
    setPage("studio");
    if (result.daily_bonus_awarded) setNotice(`${t.dailyBonus} +${result.daily_bonus_awarded} PT`);
  }

  async function refreshUser() { setUser(await api.me()); }
  async function logout() {
    try {
      await api.logout();
      setUser(null); setPage("studio");
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : t.requestFailed);
    }
  }

  if (loading) return <div className="boot"><img src="/rythm-logo.png" /><span>RyThM Music</span></div>;
  if (!user) return <PublicHome locale={locale} setLocale={setLocale} t={t} notice={notice} setNotice={setNotice} onSignedIn={signedIn} />;

  return (
    <div className="app-shell">
      <Ambient />
      <aside className="sidebar">
        <Brand compact />
        <nav>{navItems.map((item) => <button key={item.page} className={page === item.page ? "active" : ""} onClick={() => setPage(item.page)}><i>{item.mark}</i><span>{t[item.page]}</span></button>)}</nav>
        <div className="side-account"><div className="avatar">{user.username.slice(0, 1).toUpperCase()}</div><div><strong>{user.username}</strong><small>COOKIE SESSION</small></div><button onClick={logout} title={t.logout}>↗</button></div>
      </aside>
      <div className="app-main">
        <header className="app-topbar"><div><span className="signal-dot" />SYSTEM ONLINE</div><LocalePicker locale={locale} setLocale={setLocale} /><div className="top-points"><b>v0.1</b> MVP</div></header>
        {notice && <button className="toast" onClick={() => setNotice("")}>{notice}</button>}
        <main className="page">
          {page === "studio" && <Studio t={t} user={user} onNavigate={setPage} />}
          {page === "analyze" && <AnalyzePage t={t} setNotice={setNotice} />}
          {page === "generate" && <GeneratePage t={t} refreshUser={refreshUser} setNotice={setNotice} />}
          {page === "works" && <WorksPage t={t} canLike />}
          {page === "history" && <HistoryPage t={t} />}
          {page === "founder" && <FounderPage t={t} canLike />}
          {page === "account" && <AccountPage t={t} onSignedOut={() => { setUser(null); setPage("studio"); }} />}
        </main>
      </div>
    </div>
  );
}

function Ambient() { return <div className="ambient" aria-hidden="true"><i /><i /><i /></div>; }
function Brand({ compact = false }: { compact?: boolean }) {
  return <div className={`brand ${compact ? "brand--compact compact" : ""}`}>
    <img className="brand__logo" src="/rythm-logo.png" alt="RyThM Music" />
    <div className="brand__text">
      <strong>RyThM <span>Music</span></strong>
      {!compact && <small>天铭音乐工作室 · 天銘ミュージックスタジオ</small>}
    </div>
  </div>;
}
function LocalePicker({ locale, setLocale }: { locale: Locale; setLocale: (locale: Locale) => void }) {
  return <label className="language-picker" aria-label="Language">
    <span aria-hidden="true">文</span>
    <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
      <option value="zh">中文</option>
      <option value="ja">日本語</option>
      <option value="en">English</option>
    </select>
  </label>;
}

function PublicHome({ locale, setLocale, t, notice, setNotice, onSignedIn }: { locale: Locale; setLocale: (locale: Locale) => void; t: Dictionary; notice: string; setNotice: (notice: string) => void; onSignedIn: (result: AuthResponse) => void }) {
  return <main className="auth-page">
    <div className="auth-ambient auth-ambient--one" aria-hidden="true" />
    <div className="auth-ambient auth-ambient--two" aria-hidden="true" />
    <header className="auth-header"><Brand compact /><LocalePicker locale={locale} setLocale={setLocale} /></header>
    <section className="auth-card">
      <div className="auth-card__visual">
        <Brand />
        <p>{t.heroBody}</p>
        <div className="model-orbits" aria-hidden="true"><i /><i /><i /></div>
      </div>
      <AuthCard t={t} notice={notice} setNotice={setNotice} onSignedIn={onSignedIn} />
    </section>
  </main>;
}

function AuthCard({ t, notice, setNotice, onSignedIn }: { t: Dictionary; notice: string; setNotice: (notice: string) => void; onSignedIn: (result: AuthResponse) => void }) {
  const [register, setRegister] = useState(false); const [email, setEmail] = useState(""); const [username, setUsername] = useState(""); const [password, setPassword] = useState(""); const [working, setWorking] = useState(false); const [error, setError] = useState(""); const [turnstileToken, setTurnstileToken] = useState(TURNSTILE_SITE_KEY ? "" : "development-not-required"); const [turnstileReset, setTurnstileReset] = useState(0);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!turnstileToken) { setError(t.humanCheck); return; }
    setWorking(true); setError(""); setNotice("");
    try {
      if (register) {
        const result = await api.register(email, username, password, turnstileToken);
        setNotice(result.message || t.verificationSent);
        setRegister(false); setPassword("");
      } else {
        onSignedIn(await api.login(email, password, turnstileToken));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t.requestFailed);
    } finally {
      setWorking(false);
      if (TURNSTILE_SITE_KEY) {
        setTurnstileToken("");
        setTurnstileReset((value) => value + 1);
      }
    }
  }
  function changeMode(next: boolean) {
    setRegister(next); setError(""); setNotice("");
    if (TURNSTILE_SITE_KEY) { setTurnstileToken(""); setTurnstileReset((value) => value + 1); }
  }
  return <div className="auth-card__form">
    <div className="auth-tabs">
      <button className={!register ? "active" : ""} type="button" onClick={() => changeMode(false)}>{t.signIn}</button>
      <button className={register ? "active" : ""} type="button" onClick={() => changeMode(true)}>{t.signUp}</button>
    </div>
    <h1>{register ? t.signUp : t.signIn}</h1>
    <p className="auth-hint">{t.authTitle} · {t.authHint}</p>
    {notice && <div className="auth-notice success" role="status">{notice}</div>}
    {error && <div className="auth-notice" role="alert">{error}</div>}
    <form onSubmit={submit}>
      {register && <AuthField icon="◇" label={t.username} value={username} setValue={setUsername} autoComplete="username" />}
      <AuthField icon="@" label={t.email} value={email} setValue={setEmail} type="email" autoComplete="email" />
      <AuthField icon="●" label={`${t.password}${register ? " (12–128)" : ""}`} value={password} setValue={setPassword} type="password" minLength={register ? 12 : 1} autoComplete={register ? "new-password" : "current-password"} />
      <TurnstileWidget action={register ? "register" : "login"} resetKey={turnstileReset} onToken={setTurnstileToken} />
      <button className="auth-submit" disabled={working || !turnstileToken} type="submit">{working ? t.working : register ? t.signUp : t.signIn}<span aria-hidden="true">→</span></button>
    </form>
    <p className="privacy-note">✦ {t.registerBonus}</p>
  </div>;
}

type TurnstileApi = {
  ready: (callback: () => void) => void;
  render: (container: HTMLElement, options: Record<string, unknown>) => string;
  remove: (widgetId: string) => void;
};

function TurnstileWidget({ action, resetKey, onToken }: { action: "login" | "register"; resetKey: number; onToken: (token: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const callback = useRef(onToken);
  callback.current = onToken;

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY || !container.current) return;
    let canceled = false;
    let widgetId = "";
    const turnstileWindow = window as typeof window & { turnstile?: TurnstileApi };
    const renderWidget = () => turnstileWindow.turnstile?.ready(() => {
      if (canceled || !container.current || !turnstileWindow.turnstile) return;
      widgetId = turnstileWindow.turnstile.render(container.current, {
        sitekey: TURNSTILE_SITE_KEY,
        action,
        theme: "dark",
        size: "flexible",
        callback: (token: string) => callback.current(token),
        "expired-callback": () => callback.current(""),
        "error-callback": () => callback.current("")
      });
    });
    let script = document.querySelector<HTMLScriptElement>("#turnstile-script");
    if (!script) {
      script = document.createElement("script");
      script.id = "turnstile-script";
      script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
    if (turnstileWindow.turnstile) renderWidget();
    else script.addEventListener("load", renderWidget, { once: true });
    return () => {
      canceled = true;
      script?.removeEventListener("load", renderWidget);
      if (widgetId && turnstileWindow.turnstile) turnstileWindow.turnstile.remove(widgetId);
    };
  }, [action, resetKey]);

  if (!TURNSTILE_SITE_KEY) return null;
  return <div className="turnstile-slot" ref={container} />;
}

function AuthField({ icon, label, value, setValue, type = "text", minLength, autoComplete }: { icon: string; label: string; value: string; setValue: (value: string) => void; type?: string; minLength?: number; autoComplete: string }) {
  return <label className="auth-field">
    <span>{label}</span>
    <div className="auth-control"><i aria-hidden="true">{icon}</i><input required value={value} onChange={(event) => setValue(event.target.value)} type={type} minLength={minLength} maxLength={type === "password" ? 128 : undefined} autoComplete={autoComplete} /></div>
  </label>;
}

function Field({ label, value, setValue, type = "text", placeholder = "" }: { label: string; value: string; setValue: (value: string) => void; type?: string; placeholder?: string }) { return <label className="field"><span>{label}</span><input required value={value} onChange={(event) => setValue(event.target.value)} type={type} placeholder={placeholder} minLength={type === "password" ? 8 : undefined} /></label>; }

function PageTitle({ tag, title, body, actions }: { tag: string; title: string; body: string; actions?: React.ReactNode }) { return <header className="page-title"><div><p className="kicker"><span />{tag}</p><h1>{title}</h1><p>{body}</p></div>{actions}</header>; }

function Studio({ t, user, onNavigate }: { t: Dictionary; user: User; onNavigate: (page: Page) => void }) {
  const [history, setHistory] = useState<Analysis[]>([]); const [generations, setGenerations] = useState<Generation[]>([]);
  useEffect(() => { Promise.all([api.history(), api.generations()]).then(([a, g]) => { setHistory(a.items); setGenerations(g); }).catch(() => undefined); }, []);
  const activities = useMemo(() => [...history.map((item) => ({ name: item.original_filename, date: item.created_at, kind: t.analyze })), ...generations.map((item) => ({ name: item.title, date: item.created_at, kind: t.generate }))].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 6), [history, generations, t]);
  return <><PageTitle tag="CREATIVE CONTROL" title={`${t.welcome}, ${user.username}`} body={t.welcomeBody} actions={<div className="title-actions"><button className="secondary" onClick={() => onNavigate("analyze")}>{t.newAnalysis}</button><button className="primary" onClick={() => onNavigate("generate")}>{t.newGeneration}</button></div>} /><div className="stat-grid two"><Stat mark="A" label={t.analyses} value={`${history.length}`} /><Stat mark="G" label={t.generations} value={`${generations.length}`} /></div><section className="panel activity"><PanelHead title={t.latestActivity} /><div className="rows">{activities.length ? activities.map((item) => <div className="row" key={`${item.kind}-${item.date}`}><i>{item.kind.slice(0, 1)}</i><div><strong>{item.name}</strong><small>{item.kind}</small></div><time>{new Date(item.date).toLocaleDateString()}</time></div>) : <Empty text={t.noActivity} />}</div></section></>;
}

function Stat({ mark, label, value }: { mark: string; label: string; value: string }) { return <article className="stat panel"><i>{mark}</i><div><span>{label}</span><strong>{value}</strong></div><em>↗</em></article>; }
function PanelHead({ title, meta }: { title: string; meta?: string }) { return <header className="panel-head"><h2>{title}</h2>{meta && <span>{meta}</span>}</header>; }
function Empty({ text }: { text: string }) { return <div className="empty"><img src="/rythm-logo.png" /><p>{text}</p></div>; }

function AnalyzePage({ t, setNotice }: { t: Dictionary; setNotice: (text: string) => void }) {
  const input = useRef<HTMLInputElement>(null); const [file, setFile] = useState<File | null>(null); const [drag, setDrag] = useState(false); const [working, setWorking] = useState(false); const [result, setResult] = useState<Analysis | null>(null); const [error, setError] = useState("");
  function receive(files: FileList | null) { if (files?.[0]) setFile(files[0]); }
  async function run() { if (!file) return; setWorking(true); setError(""); try { setResult(await api.analyze(file)); setNotice(t.success); } catch (reason) { setError(reason instanceof Error ? reason.message : t.requestFailed); } finally { setWorking(false); } }
  function drop(event: DragEvent) { event.preventDefault(); setDrag(false); receive(event.dataTransfer.files); }
  return <><PageTitle tag="ANALYSIS / TONNETZ / ONNX" title={t.analysisLab} body={t.analysisBody} actions={<div className="top-points large"><b>ONNX</b> CPU</div>} /><section className={`upload panel ${drag ? "drag" : ""}`} onClick={() => input.current?.click()} onDragOver={(event) => { event.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={drop}><input hidden ref={input} type="file" accept=".mp3,.wav,.flac,.m4a" onChange={(event) => receive(event.target.files)} /><div className="upload-mark"><span>⌁</span></div><h2>{file ? file.name : t.drop}</h2><p>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : t.browse}</p>{file && <button className="primary" disabled={working} onClick={(event) => { event.stopPropagation(); run(); }}>{working ? t.analyzing : t.run}</button>}<div className="format-row"><span>WAV</span><span>MP3</span><span>FLAC</span><span>M4A</span></div></section>{error && <p className="error block">{error}</p>}{working && <div className="progress panel"><div /><span>{t.analyzing}</span></div>}{result && <AnalysisResult t={t} result={result} />}</>;
}

function AnalysisResult({ t, result }: { t: Dictionary; result: Analysis }) {
  async function report() { const blob = await api.report(result.id); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `rythm-analysis-${result.id}.pdf`; anchor.click(); URL.revokeObjectURL(url); }
  const genreNote = result.genre
    ? `${Math.round(Number(result.genre_confidence) * 100)}%`
    : result.genre_model_status === "MODEL_ERROR" ? t.modelError : t.modelMissing;
  return <section className="analysis-result"><div className="result-title"><div><p>ANALYSIS #{result.id}</p><h2>{result.original_filename}</h2></div><button className="secondary" onClick={report}>{t.download}</button></div><div className="metric-grid"><Metric label={t.bpm} value={formatBpm(result.bpm)} /><Metric label={t.key} value={formatMusicalKey(result.musical_key)} /><Metric label={t.genre} value={result.genre ?? t.notConfigured} note={genreNote} /><Metric label={t.loudness} value={result.lufs !== null ? `${result.lufs} LUFS` : "—"} /><Metric label={t.duration} value={formatDuration(result.duration_sec, t)} /></div><div className="visual-grid"><section className="panel"><PanelHead title={t.waveform} meta="TIME / AMP" /><Waveform values={result.waveform ?? []} /></section><section className="panel"><PanelHead title={t.spectrogram} meta="HZ / DB" /><Spectrogram values={result.spectrogram ?? []} /></section></div><div className="insight-grid"><section className="panel insight"><PanelHead title={t.aiSummary} meta={result.ai_summary_source} /><p>{result.ai_summary || t.notConfigured}</p></section><section className="panel insight"><PanelHead title={t.lyrics} meta={result.lyrics_status} /><p>{result.lyrics || t.lyricsMissing}</p></section></div></section>;
}

function Metric({ label, value, note }: { label: string; value: string | number; note?: string }) { return <article className="metric panel"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</article>; }
function Waveform({ values }: { values: number[] }) {
  const amplitudes = values.map((value) => Math.abs(Number(value))).filter(Number.isFinite);
  if (!amplitudes.length) return <svg className="waveform" viewBox="0 0 1200 180" preserveAspectRatio="none"><line x1="0" y1="90" x2="1200" y2="90" /></svg>;
  const ordered = [...amplitudes].sort((a, b) => a - b);
  const reference = ordered[Math.floor((ordered.length - 1) * .98)] || Math.max(...ordered) || 1;
  const normalized = amplitudes.map((value) => Math.min(1, value / reference));
  const width = 1200; const center = 90; const height = 78;
  const point = (value: number, index: number, direction: 1 | -1) => `${(index / Math.max(normalized.length - 1, 1)) * width},${center + direction * value * height}`;
  const upper = normalized.map((value, index) => point(value, index, -1));
  const lower = normalized.map((value, index) => point(value, index, 1)).reverse();
  const area = `M ${upper.join(" L ")} L ${lower.join(" L ")} Z`;
  return <svg className="waveform" viewBox="0 0 1200 180" preserveAspectRatio="none"><defs><linearGradient id="wave" x1="0" x2="1"><stop stopColor="#35e7ff" /><stop offset=".52" stopColor="#9d5cff" /><stop offset="1" stopColor="#ff3eb5" /></linearGradient></defs><line x1="0" y1="90" x2="1200" y2="90" /><path d={area} /></svg>;
}
function Spectrogram({ values }: { values: number[][] }) { const canvas = useRef<HTMLCanvasElement>(null); useEffect(() => { const node = canvas.current; if (!node || !values.length) return; const height = values.length; const width = Math.max(...values.map((row) => row.length)); if (!width) return; node.width = width; node.height = height; const context = node.getContext("2d"); if (!context) return; const image = context.createImageData(width, height); values.forEach((row, y) => row.forEach((value, x) => { const p = Math.max(0, Math.min(1, (value + 80) / 80)); const index = ((height - 1 - y) * width + x) * 4; image.data[index] = Math.round(25 + 230 * p); image.data[index + 1] = Math.round(10 + 85 * Math.pow(p, 2)); image.data[index + 2] = Math.round(55 + 200 * (1 - Math.abs(p - .55) * 1.7)); image.data[index + 3] = 255; })); context.putImageData(image, 0, 0); }, [values]); return <canvas ref={canvas} className="spectrogram" />; }

function GeneratePage({ t, refreshUser, setNotice }: { t: Dictionary; refreshUser: () => Promise<void>; setNotice: (text: string) => void }) {
  const [prompt, setPrompt] = useState(""); const [title, setTitle] = useState(""); const [duration, setDuration] = useState(8); const [instrumental, setInstrumental] = useState(true); const [working, setWorking] = useState(false); const [items, setItems] = useState<Generation[]>([]); const [error, setError] = useState("");
  const load = () => api.generations().then(setItems);
  useEffect(() => { load().catch(() => undefined); }, []);
  async function generate(event: FormEvent) { event.preventDefault(); setWorking(true); setError(""); try { await api.generate(prompt, title, instrumental, duration); setPrompt(""); setTitle(""); await Promise.all([load(), refreshUser()]); } catch (reason) { setError(reason instanceof Error ? reason.message : t.requestFailed); } finally { setWorking(false); } }
  return <><PageTitle tag="GENERATIVE AUDIO" title={t.generationLab} body={t.generationBody} actions={<span className="demo-pill">{t.demoBadge}</span>} /><form className="generator panel" onSubmit={generate}><div className="generator-fields"><Field label={t.titleOptional} value={title} setValue={setTitle} /><label className="field"><span>{t.prompt}</span><textarea required minLength={3} maxLength={1000} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder={t.promptExample} /></label><div className="generator-options"><label className="check"><input type="checkbox" checked={instrumental} onChange={(event) => setInstrumental(event.target.checked)} /><i />{t.instrumental}</label><label className="range"><span>{duration} {t.seconds}</span><input type="range" min="5" max="30" value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></label></div></div><div className="generator-orb"><img src="/rythm-logo.png" /><button className="primary" disabled={working}>{working ? t.working : t.create}</button></div></form>{error && <p className="error block">{error}</p>}<section className="generation-list"><PanelHead title={t.myGenerations} meta={`${items.length}`} />{items.length ? items.map((item) => <GenerationCard key={item.id} item={item} t={t} onPublished={() => setNotice(t.published)} />) : <Empty text={t.noGenerations} />}</section></>;
}

function GenerationCard({ item, t, onPublished }: { item: Generation; t: Dictionary; onPublished: () => void }) {
  const [publishing, setPublishing] = useState(false); const [description, setDescription] = useState(""); const [cover, setCover] = useState<Work["cover_gradient"]>("violet"); const [error, setError] = useState(""); const [track, setTrack] = useState(item);
  async function publish() { setError(""); try { await api.publish(item.id, item.title, description, cover); setPublishing(false); onPublished(); } catch (reason) { setError(reason instanceof Error ? reason.message : t.requestFailed); } }
  async function refresh() { setError(""); try { setTrack(await api.refreshGeneration(track.id)); } catch (reason) { setError(reason instanceof Error ? reason.message : t.requestFailed); } }
  return <article className="generation-card panel"><div className={`cover ${cover}`}><span>R</span><i /></div><div className="track-main"><div><p>{track.provider.toUpperCase()} / {track.duration_sec}s · {track.status}</p><h3>{track.title}</h3><small>{track.prompt}</small></div>{track.audio_url && <audio controls preload="none" src={track.audio_url} />}</div>{track.status === "PROCESSING" ? <button className="secondary" onClick={refresh}>↻</button> : <button className="secondary" onClick={() => setPublishing(!publishing)}>{t.publish}</button>}{publishing && <div className="publish-box"><textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder={t.description} maxLength={1000} /><select value={cover} onChange={(event) => setCover(event.target.value as Work["cover_gradient"])}><option value="violet">Violet</option><option value="cyan">Cyan</option><option value="sunset">Sunset</option><option value="midnight">Midnight</option></select><button className="primary" onClick={publish}>{t.publishNow}</button>{error && <p className="error">{error}</p>}</div>}{error && !publishing && <p className="error">{error}</p>}</article>;
}

function WorksPage({ t, canLike = false }: { t: Dictionary; canLike?: boolean }) { const [items, setItems] = useState<Work[]>([]); const [error, setError] = useState(""); useEffect(() => { api.works().then(setItems).catch((reason) => setError(reason instanceof Error ? reason.message : t.requestFailed)); }, [t]); async function like(id: number) { try { const updated = await api.like(id); setItems((current) => current.map((item) => item.id === id ? updated : item)); } catch (reason) { setError(reason instanceof Error ? reason.message : t.requestFailed); } } return <><PageTitle tag="PUBLIC FREQUENCY" title={t.community} body={t.communityBody} />{error && <p className="error block">{error}</p>}<div className="works-grid">{items.length ? items.map((item) => <WorkCard key={item.id} item={item} t={t} onLike={canLike ? () => like(item.id) : undefined} />) : <Empty text={t.noWorks} />}</div></>; }
function WorkCard({ item, t, onLike }: { item: Work; t: Dictionary; onLike?: () => void }) { return <article className="work-card panel"><div className={`work-cover ${item.cover_gradient}`}><span>RyThM</span><i>{item.title.slice(0, 1)}</i><div className="cover-grid" /></div><div className="work-info"><p>BY {item.creator_name.toUpperCase()}</p><h3>{item.title}</h3><small>{item.description || "—"}</small>{item.audio_url && <audio controls preload="none" src={item.audio_url} />}<button disabled={!onLike} onClick={onLike}>♡ {item.likes_count} · {t.like}</button></div></article>; }

function HistoryPage({ t }: { t: Dictionary }) { const [items, setItems] = useState<Analysis[]>([]); const [selected, setSelected] = useState<Analysis | null>(null); useEffect(() => { api.history().then((data) => setItems(data.items)).catch(() => undefined); }, []); return <><PageTitle tag="AUDIO ARCHIVE" title={t.historyTitle} body={t.historyBody} /><section className="panel history-table">{items.length ? items.map((item) => <button className="history-row" key={item.id} onClick={() => setSelected(item)}><i>{item.file_format.toUpperCase()}</i><div><strong>{item.original_filename}</strong><small>{new Date(item.created_at).toLocaleString()}</small></div><span>{item.genre || item.genre_model_status}</span><b>{formatBpm(item.bpm)} BPM</b><em>{item.status === "SUCCESS" ? t.success : t.failed}</em></button>) : <Empty text={t.noHistory} />}</section>{selected && <AnalysisResult t={t} result={selected} />}</>; }

function AccountPage({ t, onSignedOut }: { t: Dictionary; onSignedOut: () => void }) {
  const [sessions, setSessions] = useState<BrowserSession[]>([]);
  const [error, setError] = useState("");
  const load = () => api.sessions().then(setSessions).catch((reason) => setError(reason instanceof Error ? reason.message : t.requestFailed));
  useEffect(() => { void load(); }, [t]);
  async function revoke(session: BrowserSession) {
    try {
      await api.revokeSession(session.id);
      if (session.current) onSignedOut();
      else await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t.requestFailed);
    }
  }
  async function logoutEverywhere() {
    try {
      await api.logoutAll();
      onSignedOut();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t.requestFailed);
    }
  }
  return <>
    <PageTitle tag="SESSION CONTROL" title={t.securityTitle} body={t.securityBody} actions={<button className="secondary danger" onClick={logoutEverywhere}>{t.revokeAll}</button>} />
    {error && <p className="error block">{error}</p>}
    <section className="panel session-panel">
      <PanelHead title={t.devices} />
      <div className="session-list">
        {sessions.map((session) => <article className="session-row" key={session.id}>
          <div className="session-icon">◇</div>
          <div>
            <strong>{session.user_agent || t.unknownDevice}</strong>
            <small>{session.ip_address || "—"} · {t.lastSeen} {new Date(session.last_seen_at).toLocaleString()}</small>
          </div>
          {session.current && <span>{t.currentDevice}</span>}
          <button className="secondary danger" onClick={() => revoke(session)}>{t.revoke}</button>
        </article>)}
      </div>
    </section>
  </>;
}

function FounderPage({ t, canLike = false }: { t: Dictionary; canLike?: boolean }) { const [profile, setProfile] = useState<Founder | null>(null); const [works, setWorks] = useState<Work[]>([]); useEffect(() => { Promise.all([api.founder(), api.works()]).then(([founder, rows]) => { setProfile(founder); setWorks(rows.filter((item) => item.creator_name.toLowerCase() === "rythm")); }).catch(() => undefined); }, []); async function like(id: number) { const updated = await api.like(id); setWorks((current) => current.map((item) => item.id === id ? updated : item)); } return <><section className="founder-hero panel"><div className="founder-portrait"><img src="/rythm-logo.png" /><i /></div><div><p className="kicker"><span />{t.founderTag}</p><h1>{t.founderTitle}</h1><blockquote>“{profile?.tagline || "Between machine precision and human rhythm."}”</blockquote><p>{profile?.bio || t.founderFallback}</p><div className="style-tags">{(profile?.styles || ["Electronic", "Cyberpunk"]).map((style) => <span key={style}>{style}</span>)}</div></div></section><section className="founder-tracks"><PanelHead title={t.founderWorks} />{works.length ? <div className="works-grid">{works.map((item) => <WorkCard key={item.id} item={item} t={t} onLike={canLike ? () => like(item.id) : undefined} />)}</div> : <Empty text={t.founderEmpty} />}</section></>; }
