// mkexam TypeScript 前端 — 强类型 + Apple 设计风格

// ═══════════════════════════════════════════════════════
//  类型定义
// ═══════════════════════════════════════════════════════

interface Question {
  id: string;
  type: string;
  q: string;
  opts: string[];
  ans: string;
  explain: string;
  difficulty: number;
  ch: string;
  text?: string;
  options?: string[];
  answer?: string;
  image?: string;
  /** 服务端渲染后的纯文本公式 */
  q_plain?: string;
  /** 服务端渲染后的选项文本 */
  opts_plain?: string[];
  /** 图片 URL */
  image_url?: string;
}

interface SubjectData {
  name: string;
  questions: Question[];
  counts: Record<string, number>;
}

interface SectionConfig {
  title: string;
  key: string;
  count: number;
  score: number;
}

interface Presets {
  [name: string]: SectionConfig[];
}

interface RowState {
  key: string;
  countInput: HTMLInputElement;
  scoreInput: HTMLInputElement;
  subtotalEl: HTMLElement;
}

// 试卷头部信息接口
interface ExamHeader {
  course: string;
  year: string;
  dept: string;
  author: string;
  reviewer: string;
  political: string;
}

// 科目显示名映射
const SUBJECT_NAMES: Record<string, string> = {
  "单片机技术": "单片机技术及应用",
  "电工电子技术": "电工电子技术",
};

function toggleHeaderForm(): void {
  const form = document.getElementById("header-form");
  const toggle = document.getElementById("header-toggle");
  if (!form || !toggle) return;
  const isOpen = form.style.display !== "none";
  form.style.display = isOpen ? "none" : "block";
  toggle.textContent = isOpen ? "展开" : "收起";
}

function getHeaderInfo(): ExamHeader {
  return {
    course: (document.getElementById("h-course") as HTMLInputElement)?.value || "",
    year: (document.getElementById("h-year") as HTMLInputElement)?.value || "",
    dept: (document.getElementById("h-dept") as HTMLInputElement)?.value || "",
    author: (document.getElementById("h-author") as HTMLInputElement)?.value || "",
    reviewer: (document.getElementById("h-reviewer") as HTMLInputElement)?.value || "",
    political: (document.getElementById("h-political") as HTMLInputElement)?.value || "",
  };
}

// ═══════════════════════════════════════════════════════
//  API 调用
// ═══════════════════════════════════════════════════════

async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = { method };
  if (body) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`API ${method} ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

const GET = <T>(path: string) => api<T>("GET", path);
const POST = <T>(path: string, body: unknown) => api<T>("POST", path, body);

// ═══════════════════════════════════════════════════════
//  工具函数
// ═══════════════════════════════════════════════════════

const TYPE_NAMES: Record<string, string> = {
  choice: "选择题", tf: "判断题", fill: "填空题",
  calc: "计算题", short: "简答题", analysis: "分析题",
  "分析题": "分析题", "应用题": "应用题", "应用分析题": "应用分析题",
};

const CN_NUMS = ["一", "二", "三", "四", "五", "六"];

function renderFormula(text: string): string {
  // 将 $...$ 转为可读文本
  return text.replace(/\$([^$]+)\$/g, (_: string, inner: string) => {
    return inner
      .replace(/\\cdot/g, "·")
      .replace(/\\oplus/g, "⊕")
      .replace(/\\overline\{([^}]+)\}/g, "$1̄")
      .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, "$1/$2")
      .replace(/_\{?([A-Za-z0-9]+)\}?/g, (_: string, s: string) => "_" + s);
  });
}

function escHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function getImageUrl(q: Question): string | null {
  if (q.image) return q.image;
  // 使用服务端返回的 image_url
  if (q.image_url) return q.image_url;
  return null;
}

function hasAnswerSheet(): boolean {
  const cb = document.getElementById("has-answer-sheet") as HTMLInputElement;
  return cb ? cb.checked : true;
}

// ═══════════════════════════════════════════════════════
//  状态
// ═══════════════════════════════════════════════════════

let currentSubject = "";
let currentQuestions: Question[] = [];
let currentFilter = "";
let tabRows: RowState[] = [];
let currentSelected: Record<string, Question[]> = {};
let currentSections: SectionConfig[] = [];

// ═══════════════════════════════════════════════════════
//  Tab 切换
// ═══════════════════════════════════════════════════════

function switchTab(name: string): void {
  document.querySelectorAll(".tab-content").forEach(e => (e as HTMLElement).style.display = "none");
  document.querySelectorAll(".tab-btn").forEach(e => e.classList.remove("active"));
  const content = document.getElementById(`tab-${name}`);
  if (content) content.style.display = "block";
  const btn = document.querySelector(`.tab-btn[data-tab="${name}"]`);
  if (btn) btn.classList.add("active");
}

// ═══════════════════════════════════════════════════════
//  Tab 1: 题库浏览
// ═══════════════════════════════════════════════════════

async function loadBank(): Promise<void> {
  const subjects = await GET<string[]>("/api/subjects");
  const list = document.getElementById("subject-list")!;
  list.innerHTML = "";
  for (const name of subjects) {
    const btn = document.createElement("button");
    btn.className = "subject-btn";
    btn.textContent = name;
    btn.onclick = () => loadSubject(name);
    list.appendChild(btn);
  }
  if (subjects.length > 0) loadSubject(subjects[0]);
}

async function loadSubject(name: string): Promise<void> {
  currentSubject = name;
  document.querySelectorAll(".subject-btn").forEach(e => e.classList.remove("active"));
  const btns = document.querySelectorAll<HTMLButtonElement>(".subject-btn");
  for (const b of btns) {
    if (b.textContent === name) b.classList.add("active");
  }
  const data = await GET<SubjectData>(`/api/subject?name=${encodeURIComponent(name)}`);
  currentQuestions = data.questions;
  currentFilter = "";
  renderTypeFilters(data.counts);
  renderQuestions(data.questions);
}

function renderTypeFilters(counts: Record<string, number>): void {
  const container = document.getElementById("type-filters")!;
  container.innerHTML = `<button class="tab-btn ${currentFilter === "" ? "active" : ""}" onclick="setTypeFilter('')">全部</button>`;
  // 遍历 counts 中所有类型（含自定义类型如 分析题、应用题）
  for (const key of Object.keys(counts).sort()) {
    const name = TYPE_NAMES[key] || key;
    container.innerHTML += `<button class="tab-btn ${currentFilter === key ? "active" : ""}" onclick="setTypeFilter('${key}')">${name} (${counts[key]})</button>`;
  }
}

function setTypeFilter(key: string): void {
  currentFilter = key;
  renderQuestions(currentQuestions);
}

function renderQuestions(questions: Question[]): void {
  const filtered = currentFilter ? questions.filter(q => q.type === currentFilter) : questions;
  const container = document.getElementById("question-list")!;
  container.innerHTML = "";
  if (filtered.length === 0) {
    container.innerHTML = "<div class='preview-msg'>无题目</div>";
    return;
  }
  for (const q of filtered) {
    const card = document.createElement("div");
    card.className = "q-card";

    const typeLabel = document.createElement("span");
    typeLabel.className = "q-type";
    typeLabel.textContent = TYPE_NAMES[q.type] || q.type;
    card.appendChild(typeLabel);

    const textEl = document.createElement("div");
    const plainText = q.q_plain || renderFormula(q.q || q.text || "");
    // 应用设计 / 代码题用等宽字体 + 保留格式
    if (q.type === "应用分析题" || q.type === "应用题" || /#include|void main|sbit|while\(/.test(plainText)) {
      textEl.className = "q-text code";
      textEl.textContent = plainText;
    } else {
      textEl.className = "q-text";
      textEl.textContent = plainText;
    }
    card.appendChild(textEl);

    // 选项
    const opts = q.opts_plain || q.opts || q.options || [];
    if (opts.length > 0) {
      const optList = document.createElement("div");
      optList.className = "q-opts";
      for (let i = 0; i < Math.min(opts.length, 4); i++) {
        const o = document.createElement("div");
        o.textContent = `${String.fromCharCode(65 + i)}. ${opts[i]}`;
        optList.appendChild(o);
      }
      card.appendChild(optList);
    }

    // 图片
    const imgUrl = q.image_url;
    if (imgUrl) {
      const img = document.createElement("img");
      img.className = "q-img";
      img.src = imgUrl;
      img.alt = "配图";
      card.appendChild(img);
    }

    container.appendChild(card);
  }
}

// ═══════════════════════════════════════════════════════
//  Tab 2: 组卷
// ═══════════════════════════════════════════════════════

async function loadExamConfig(): Promise<void> {
  const subjects = await GET<string[]>("/api/subjects");
  const sel = document.getElementById("exam-subject") as HTMLSelectElement;
  sel.innerHTML = "";
  for (const name of subjects) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = SUBJECT_NAMES[name] || name;
    sel.appendChild(opt);
  }
  if (subjects.length > 0) {
    sel.value = subjects[0];
    onExamSubjectChange();
  }
  sel.onchange = onExamSubjectChange;
}

async function onExamSubjectChange(): Promise<void> {
  const name = (document.getElementById("exam-subject") as HTMLSelectElement).value;
  if (!name) return;
  const data = await GET<SubjectData>(`/api/subject?name=${encodeURIComponent(name)}`);
  // 设置头部默认值
  const displayName = SUBJECT_NAMES[name] || name;
  const hCourse = document.getElementById("h-course") as HTMLInputElement;
  const hYear = document.getElementById("h-year") as HTMLInputElement;
  if (hCourse) hCourse.value = displayName;
  if (hYear) hYear.value = name.includes("电工") ? "2025" : "2024";
  const rows = document.getElementById("type-rows")!;
  rows.innerHTML = "";
  tabRows = [];

  const counts = data.counts;
  const defaults: Record<string, [number, number]> = {
    choice: [15, 2], tf: [5, 2], fill: [5, 2],
    short: [5, 6], calc: [5, 10], analysis: [2, 10], "应用分析题": [2, 10],
  };

  // 遍历全部题型（含自定义）
  const predefinedKeys = ["choice", "tf", "fill", "short", "calc", "analysis"];
  const seenKeys = new Set(predefinedKeys);
  const allKeys = [...predefinedKeys, ...Object.keys(counts).filter(k => !seenKeys.has(k))];

  for (const key of allKeys) {
    const avail = counts[key] || 0;
    if (avail === 0) continue;

    const row = document.createElement("div");
    row.className = "cfg-row";

    const defaultCount = defaults[key]?.[0] || 2;
    const defaultScore = defaults[key]?.[1] || 10;

    row.innerHTML = `
      <span class="cfg-label">${TYPE_NAMES[key] || key}</span>
      <span class="cfg-avail">库存 ${avail} 题</span>
      <input type="number" class="cfg-input" value="${defaultCount}" min="0" max="${avail}">
      <span class="cfg-x">×</span>
      <input type="number" class="cfg-input" value="${defaultScore}" min="0" max="50">
      <span class="cfg-label">分</span>
      <span class="cfg-subtotal">0</span>
    `;

    const countInput = row.querySelectorAll("input")[0] as HTMLInputElement;
    const scoreInput = row.querySelectorAll("input")[1] as HTMLInputElement;
    const subtotalEl = row.querySelector(".cfg-subtotal") as HTMLElement;

    countInput.oninput = () => updateTotal();
    scoreInput.oninput = () => updateTotal();

    rows.appendChild(row);
    tabRows.push({ key, countInput, scoreInput, subtotalEl });
  }
  updateTotal();
}

function updateTotal(): void {
  let total = 0;
  let ctTotal = 0;
  for (const r of tabRows) {
    const c = parseInt(r.countInput.value) || 0;
    const s = parseInt(r.scoreInput.value) || 0;
    const sub = c * s;
    r.subtotalEl.textContent = String(sub);
    total += sub;
    if (r.key === "choice" || r.key === "tf") ctTotal += sub;
  }
  document.getElementById("total-score")!.textContent = String(total);
  const ctEl = document.getElementById("ct-score")!;
  ctEl.textContent = String(ctTotal);
  if (ctTotal > 40) {
    ctEl.style.color = "#d32f2f";
  } else {
    ctEl.style.color = "#1d1d1f";
  }
}

interface PreviewItem {
  text: string;
  opts: string[];
  image: string | null;
}

interface PreviewData {
  [typeKey: string]: {
    title: string;
    questions: PreviewItem[];
    count: number;
    score: number;
    total: number;
  };
}

// 组卷验证
async function validateExam(subject: string, sections: SectionConfig[]): Promise<boolean> {
  try {
    const resp = await POST("/api/validate", { subject, sections });
    const data = resp as any;
    if (data.all_ok) return true;
    let msg = "组卷失败，以下题型库存不足：\n";
    for (const [key, info] of Object.entries(data)) {
      if (key === "all_ok") continue;
      const d = info as { avail: number; need: number; ok: boolean };
      if (!d.ok) {
        const name = TYPE_NAMES[key] || key;
        msg += `  ${name}: 需要${d.need}题，可用仅${d.avail}题\n`;
      }
    }
    alert(msg);
    return false;
  } catch(e) {
    return true; // 验证失败时放行
  }
}

// 获取当前组卷配置
function getExamSections(): SectionConfig[] | null {
  const sections: SectionConfig[] = [];
  for (const r of tabRows) {
    const c = parseInt(r.countInput.value) || 0;
    const s = parseInt(r.scoreInput.value) || 0;
    if (c <= 0 || s <= 0) continue;
    sections.push({ title: "", key: r.key, count: c, score: s });
  }
  return sections.length > 0 ? sections : null;
}

// 显示 mammoth 预览
async function showDocxPreview(areaId: string, docxFilename: string): Promise<void> {
  const area = document.getElementById(areaId);
  if (!area) return;
  area.style.display = "block";
  area.innerHTML = "<div class='spinner'>加载预览...</div>";
  try {
    const resp = await fetch(`/api/preview-docx/${encodeURIComponent(docxFilename)}?t=${Date.now()}`);
    if (resp.ok) {
      const wordHtml = await resp.text();
      area.innerHTML = `<div style="font-family:'Times New Roman',serif;font-size:12pt;line-height:1.8;padding:20px">${wordHtml}</div>`;
    } else {
      area.innerHTML = `<div class="preview-msg" style="color:#ff3b30">预览加载失败</div>`;
    }
  } catch(e) {
    area.innerHTML = `<div class="preview-msg" style="color:#ff3b30">预览加载失败: ${e}</div>`;
  }
}

// 1) 预览题目
async function previewQuestions(): Promise<void> {
  const subject = (document.getElementById("exam-subject") as HTMLSelectElement).value;
  if (!subject) return alert("请选择科目");
  const sections = getExamSections();
  if (!sections) return alert("请配置至少一种题型");

  const ctTotal = sections.filter(s => s.key === "choice" || s.key === "tf")
    .reduce((t, s) => t + s.count * s.score, 0);
  if (ctTotal > 40) {
    if (!confirm(`选择+判断总分 ${ctTotal} 分，超过 40 分限制，仍要继续？`)) return;
  }

  currentSections = sections;
  const preview = document.getElementById("exam-preview")!;
  preview.innerHTML = "<div class='spinner'>抽题中...</div>";

  try {
    const data = await POST<PreviewData>("/api/preview", { subject, sections });
    let html = "";
    let grandTotal = 0;
    for (const [key, sec] of Object.entries(data)) {
      grandTotal += sec.total;
      html += `<div style="font-weight:600;margin:12px 0 6px;font-size:15px">${sec.title}（${sec.count}题 × ${sec.score}分 = ${sec.total}分）</div>`;
      for (let i = 0; i < sec.questions.length; i++) {
        const q = sec.questions[i];
        html += `<div style="padding:6px 0;border-bottom:1px solid #f0f0f0">`;
        html += `<div style="font-size:13px">${i+1}. ${escHtml(q.text)}</div>`;
        if (q.image) {
          html += `<img src="${q.image}" style="max-width:100%;max-height:240px;margin:6px 0;border-radius:8px;border:1px solid #d2d2d7;display:block" onerror="this.style.display='none'">`;
        }
        if (q.opts.length > 0) {
          for (let oi = 0; oi < q.opts.length; oi++) {
            html += `<div style="font-size:12px;color:#86868b;padding-left:16px">${String.fromCharCode(65+oi)}. ${escHtml(q.opts[oi])}</div>`;
          }
        }
        html += `</div>`;
      }
    }
    html += `<div style="font-weight:700;font-size:16px;margin-top:16px;padding-top:12px;border-top:2px solid #d2d2d7">总分: ${grandTotal} 分</div>`;
    html += `<div class="btn-group" style="margin-top:12px"><button class="btn btn-primary" onclick="doGenerate()">💾 保存下载</button></div>`;
    preview.innerHTML = html;
  } catch (e) {
    preview.innerHTML = `<div class="preview-msg" style="color:#ff3b30">错误: ${e}</div>`;
  }
}

// 2) 预览Word
async function previewWord(): Promise<void> {
  const subject = (document.getElementById("exam-subject") as HTMLSelectElement).value;
  if (!subject) return alert("请选择科目");
  const sections = getExamSections();
  if (!sections) return alert("请配置至少一种题型");
  if (!(await validateExam(subject, sections))) return;
  currentSections = sections;

  const preview = document.getElementById("exam-preview")!;
  preview.innerHTML = "<div class='spinner'>生成Word预览...</div>";
  try {
    const result = await POST<{ ok: boolean; output: string[] }>("/api/generate", { subject, sections: currentSections, count: 1, label: "preview", header: getHeaderInfo(), hasAnswerSheet: hasAnswerSheet() });
    const docxFile = (result.output || []).find((f: string) => f.endsWith('preview卷.docx') && !f.includes('评分标准'));
    if (!docxFile) { preview.innerHTML = "<div class='preview-msg'>未生成Word文件</div>"; return; }
    preview.innerHTML = `<div id="word-preview-area" style="border:1px solid #d2d2d7;border-radius:10px;padding:16px;background:#fff;max-height:700px;overflow:auto;text-align:left"></div>`;
    await showDocxPreview("word-preview-area", docxFile);
  } catch(e) {
    preview.innerHTML = `<div class="preview-msg" style="color:#ff3b30">生成失败: ${e}</div>`;
  }
}

// 3) 预览评分标准
async function previewScoring(): Promise<void> {
  const subject = (document.getElementById("exam-subject") as HTMLSelectElement).value;
  if (!subject) return alert("请选择科目");
  const sections = getExamSections();
  if (!sections) return alert("请配置至少一种题型");
  if (!(await validateExam(subject, sections))) return;
  currentSections = sections;

  const preview = document.getElementById("exam-preview")!;
  preview.innerHTML = "<div class='spinner'>生成评分标准预览...</div>";
  try {
    const result = await POST<{ ok: boolean; output: string[] }>("/api/generate", { subject, sections: currentSections, count: 1, label: "preview", header: getHeaderInfo(), hasAnswerSheet: hasAnswerSheet() });
    const docxFile = (result.output || []).find((f: string) => f.endsWith('preview卷评分标准.docx'));
    if (!docxFile) { preview.innerHTML = "<div class='preview-msg'>未生成评分标准文件</div>"; return; }
    preview.innerHTML = `<div id="scoring-preview-area" style="border:1px solid #d2d2d7;border-radius:10px;padding:16px;background:#fff;max-height:700px;overflow:auto;text-align:left"></div>`;
    await showDocxPreview("scoring-preview-area", docxFile);
  } catch(e) {
    preview.innerHTML = `<div class="preview-msg" style="color:#ff3b30">生成失败: ${e}</div>`;
  }
}

async function doGenerate(): Promise<void> {
  const subject = (document.getElementById("exam-subject") as HTMLSelectElement).value;
  if (!subject) return alert("请选择科目");
  const sections = getExamSections();
  if (!sections) return alert("请配置至少一种题型");
  if (!(await validateExam(subject, sections))) return;
  const n = parseInt((document.getElementById("exam-count") as HTMLInputElement).value) || 1;
  const preview = document.getElementById("exam-preview")!;
  preview.innerHTML = "<div class='spinner'>生成中...</div>";

  try {
    const result = await POST<{ ok: boolean; output: string[] }>("/api/generate", { subject, sections: currentSections, count: n, header: getHeaderInfo(), hasAnswerSheet: hasAnswerSheet() });
    let html = `<div class="preview-msg"><div class="preview-icon">✅</div><div>${n} 份试卷已生成</div><div style="margin-top:8px">`;
    const files = result.output || [];
    const docxFiles = files.filter((f: string) => f.endsWith('.docx'));
    if (docxFiles.length > 0) {
      html += '<div style="font-size:13px;color:#1d1d1f;margin:8px 0;font-weight:600">下载文件：</div>';
      for (const f of docxFiles) {
        html += `<div style="margin:4px 0"><a href="/api/output/${encodeURIComponent(f)}" download style="color:#0071e3;text-decoration:none;font-size:13px">📄 ${f}</a></div>`;
      }
    }
    html += '</div>';
    preview.innerHTML = html;
  } catch (e) {
    preview.innerHTML = `<div class="preview-msg" style="color:#ff3b30">错误: ${e}</div>`;
  }
}

async function batchGenerate(): Promise<void> {
  const subject = (document.getElementById("exam-subject") as HTMLSelectElement).value;
  if (!subject) return alert("请选择科目");
  const sections = getExamSections();
  if (!sections) return alert("请配置至少一种题型");
  if (!(await validateExam(subject, sections))) return;
  currentSections = sections;

  const n = parseInt((document.getElementById("exam-count") as HTMLInputElement).value) || 2;
  if (n < 1 || n > 10) return alert("份数范围为 1-10");

  const preview = document.getElementById("exam-preview")!;
  preview.innerHTML = "<div class='spinner'>批量出卷中...</div>";
  try {
    const result = await POST<{ ok: boolean; output: string[] }>("/api/generate", { subject, sections: currentSections, count: n, header: getHeaderInfo(), hasAnswerSheet: hasAnswerSheet() });
    const docxFiles = (result.output || []).filter((f: string) => f.endsWith('.docx') && !f.includes('preview'));
    let html = `<div class="preview-msg"><div class="preview-icon">✅</div><div>${n} 份试卷已生成</div><div style="margin-top:8px">`;
    if (docxFiles.length > 0) {
      html += '<div style="font-size:13px;color:#1d1d1f;margin:8px 0;font-weight:600">下载文件：</div>';
      for (const f of docxFiles) {
        html += `<div style="margin:4px 0"><a href="/api/output/${encodeURIComponent(f)}" download style="color:#0071e3;text-decoration:none;font-size:13px">📄 ${f}</a></div>`;
      }
    }
    html += '</div>';
    preview.innerHTML = html;
  } catch(e) {
    preview.innerHTML = `<div class="preview-msg" style="color:#ff3b30">生成失败: ${e}</div>`;
  }
}

// ═══════════════════════════════════════════════════════
//  编辑功能
// ═══════════════════════════════════════════════════════

let uploadedImageUrl = "";

async function uploadImage(): Promise<void> {
  const fileInput = document.getElementById("edit-img-file") as HTMLInputElement;
  const file = fileInput.files?.[0];
  if (!file) return alert("请选择图片文件");

  // 读取为 base64
  const reader = new FileReader();
  reader.onload = async () => {
    const base64 = reader.result as string;
    try {
      const res = await fetch("/api/upload/image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base64, subject: (document.getElementById("edit-subject") as HTMLSelectElement).value })
      });
      const data = await res.json();
      if (data.ok) {
        uploadedImageUrl = data.url;
        (document.getElementById("edit-img-url") as HTMLInputElement).value = data.url;
        const preview = document.getElementById("edit-img-preview") as HTMLElement;
        preview.style.display = "block";
        preview.querySelector("img")!.src = data.url;
      } else {
        alert("上传失败");
      }
    } catch (e) {
      alert("上传失败: " + e);
    }
  };
  reader.readAsDataURL(file);
}

// 粘贴图片（支持 Ctrl+V）
document.addEventListener("paste", async (e: ClipboardEvent) => {
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of Array.from(items)) {
    if (item.type.startsWith("image/")) {
      e.preventDefault();
      const file = item.getAsFile();
      if (!file) continue;
      // 上传图片
      const reader = new FileReader();
      reader.onload = async () => {
        const base64 = reader.result as string;
        try {
          const res = await fetch("/api/upload/image", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ base64 })
          });
          const data = await res.json();
          if (data.ok) {
            uploadedImageUrl = data.url;
            (document.getElementById("edit-img-url") as HTMLInputElement).value = data.url;
            const preview = document.getElementById("edit-img-preview") as HTMLElement;
            preview.style.display = "block";
            preview.querySelector("img")!.src = data.url;
          }
        } catch {}
      };
      reader.readAsDataURL(file);
      break;
    }
  }
});

// 粘贴图片URL时预览
document.addEventListener("DOMContentLoaded", () => {
  const urlInput = document.getElementById("edit-img-url");
  if (urlInput) {
    urlInput.addEventListener("input", () => {
      const url = (urlInput as HTMLInputElement).value.trim();
      const preview = document.getElementById("edit-img-preview") as HTMLElement;
      if (url) {
        preview.style.display = "block";
        preview.querySelector("img")!.src = url;
      } else {
        preview.style.display = "none";
      }
    });
  }
}, { once: false });

async function loadEditSubjects(): Promise<void> {
  const subjects = await GET<string[]>("/api/subjects");
  const sel = document.getElementById("edit-subject") as HTMLSelectElement;
  sel.innerHTML = "";
  for (const name of subjects) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  }
}

async function addQuestion(): Promise<void> {
  const subject = (document.getElementById("edit-subject") as HTMLSelectElement).value;
  const type = (document.getElementById("edit-type") as HTMLSelectElement).value;
  const ch = (document.getElementById("edit-ch") as HTMLInputElement).value.trim();
  const q = (document.getElementById("edit-q") as HTMLTextAreaElement).value.trim();
  const ans = (document.getElementById("edit-ans") as HTMLInputElement).value.trim();
  const diff = parseInt((document.getElementById("edit-diff") as HTMLSelectElement).value) || 2;

  if (!q) return alert("请输入题干");

  const optsText = (document.getElementById("edit-opts") as HTMLTextAreaElement).value.trim();
  const opts = optsText ? optsText.split("\n").map(l => l.replace(/^[A-E][.、]\s*/, "").trim()).filter(Boolean) : [];

  try {
    const imgUrl = (document.getElementById("edit-img-url") as HTMLInputElement).value.trim() || uploadedImageUrl;
    const result = await POST<{ ok: boolean; id: string }>("/api/question/add", {
      subject,
      question: { type, q, opts, ans, ch, difficulty: diff, image: imgUrl }
    });
    document.getElementById("edit-msg")!.textContent = `✅ 已添加: ${result.id}`;
  } catch (e) {
    document.getElementById("edit-msg")!.textContent = `❌ 失败: ${e}`;
  }
}

async function loadImportFile(): Promise<void> {
  const fileInput = document.getElementById("import-file") as HTMLInputElement;
  const file = fileInput.files?.[0];
  if (!file) return;
  const text = await file.text();
  (document.getElementById("import-csv") as HTMLTextAreaElement).value = text;
}

// 绑定文件选择事件
document.addEventListener("DOMContentLoaded", () => {
  const fi = document.getElementById("import-file");
  if (fi) fi.addEventListener("change", loadImportFile);
}, { once: false });

async function batchImport(): Promise<void> {
  const subject = (document.getElementById("edit-subject") as HTMLSelectElement).value;
  const csv = (document.getElementById("import-csv") as HTMLTextAreaElement).value.trim();
  if (!csv) return alert("请输入 CSV 数据");

  const lines = csv.split("\n").filter(Boolean);
  const header = lines[0].toLowerCase().split(",");
  const questions: Array<{type:string;ch:string;q:string;opts:string[];ans:string;difficulty:number}> = [];

  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",");
    if (cols.length < 2) continue;
    const q: {type:string;ch:string;q:string;opts:string[];ans:string;difficulty:number} = {
      type: cols[0]?.trim() || "choice",
      ch: cols[1]?.trim() || "",
      q: cols[2]?.trim() || "",
      opts: [],
      ans: cols[7]?.trim() || "",
      difficulty: parseInt(cols[8]?.trim()) || 1,
    };
    for (let j = 0; j < 4; j++) {
      if (cols[3 + j]?.trim()) q.opts.push(cols[3 + j].trim());
    }
    questions.push(q);
  }

  try {
    const result = await POST<{ ok: boolean; count: number }>("/api/question/batch", {
      subject, questions
    });
    document.getElementById("import-msg")!.textContent = `✅ 导入 ${result.count} 题`;
  } catch (e) {
    document.getElementById("import-msg")!.textContent = `❌ 失败: ${e}`;
  }
}

// ═══════════════════════════════════════════════════════
//  初始化
// ═══════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", async () => {
  loadBank();
  loadExamConfig();
  loadEditSubjects();
});
