// 입고 알림 화면(2026-11-27) — 로그인 팝오버의 종 버튼으로 진입.
// "어느 창고에 어떤 상품이 들어오면 누구에게 알림" 규칙을 서버에 저장하고,
// 파이프라인(pipeline/notify.py)이 매분 감지해 쌓은 알림을 받은 알림 목록·종 배지로 보여준다.
import { state } from "./state.js";
import { apiFetch } from "./api.js";
import { getStoredUser } from "./login.js";
import { showToast, showError, showConfirm } from "./ui.js";
import { BRAND_ALIASES } from "./table.js";

const COND_FIELDS = ["상품명", "브랜드", "등급", "ESTNO"];

// 등급 코드 → 한글 표기들(2026-11-27 사용자 제공). 입력칸엔 코드·한글 다 쓸 수 있고 저장은 코드로.
// 첫 번째 표기가 화면 라벨. 같은 한글이 여러 코드에 걸리면(셀렉트=SE/SEL, 피에스에이=PSA/PSA(RRA))
// 먼저 나온 코드로 바꾼다 — 다른 쪽은 코드로 직접 고르면 됨.
const GRADE_KO = {
    "2P": ["투피"], "3P": ["스리피", "쓰리피"], "4P": ["포피"], A: ["에이자", "에이"], AAA: ["쓰리에이", "스리에이"],
    B: ["비"], CAB: ["씨에이비", "시에이비"], CH: ["초이스"], GF: ["곡물"], PR: ["프라임"], PRE: ["프리미엄"],
    PS: ["피에스", "피애스"], PSA: ["피에스에이"], "PSA(RRA)": ["피에스에이"], RRA: ["알알에이"],
    S: ["스티어", "싙어"], SBA: ["에스비에이"], SE: ["셀렉트"], SEL: ["셀렉트"], SS: ["더블에스"],
    T: ["티자"], TCH: ["티초이스"], TOPCH: ["탑초이스"], UN: ["언그레이드"], YP: ["와이피"],
};
const GRADE_NAMES = Object.fromEntries(Object.entries(GRADE_KO).map(([code, kos]) => [code, kos[0]]));
function toGradeCode(input) {
    const v = String(input ?? "").trim();
    const hit = Object.entries(GRADE_KO).find(([, kos]) => kos.includes(v));
    return hit ? hit[0] : v.toUpperCase();
}
const gradeLabel = code => GRADE_NAMES[code] ? `${code}(${GRADE_NAMES[code]})` : code;

const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const norm = s => String(s ?? "").replace(/​/g, "").trim().toUpperCase();
const userName = () => getStoredUser()?.이름 || "";

// 받은 알림 행 클릭 → 재고장에서 그 상품 선택 후 예약 창 열기(2026-11-27).
// 탭 전환·선택 로직은 events.js에 있어서 순환 import 대신 콜백으로 받는다.
let navigateToItem = null;
export function setNotifyNavigator(fn) { navigateToItem = fn; }
let lastInbox = new Map();
// pipeline/notify.py item_key("azy_inventory:ID" / "inventory:ID") → 화면 state.allData의 id
const toStateId = key => {
    const [table, ...rest] = String(key || "").split(":");
    const raw = rest.join(":");
    if (!raw) return "";
    return table === "azy_inventory" ? `azy:${raw}` : raw;
};

// 받는 사람 후보 = 내 부서(팀) 사람만(2026-11-27). 부서가 없으면 나만. 서버(create_rule)도 같은 규칙으로 검사.
// 직급 높은 순 → 같은 직급은 이름 가나다순(목록에 없는 직급은 맨 뒤)
const RANK_ORDER = ["대표이사", "총괄", "팀장", "대리", "주임", "사원"];
const rankOf = e => { const i = RANK_ORDER.indexOf(e?.직급); return i < 0 ? RANK_ORDER.length : i; };
function teamNames() {
    const me = getStoredUser();
    if (!me) return [];
    const team = me.부서 ? state.employees.filter(e => e.부서 === me.부서) : [];
    if (!team.some(e => e.이름 === me.이름)) team.push(me);
    return team
        .sort((a, b) => rankOf(a) - rankOf(b) || a.이름.localeCompare(b.이름, "ko"))
        .map(e => e.이름);
}

// 현재 재고에 있는 값 목록(창고 칩, 입력칸 자동완성용) — 이고 표시행은 제외
function distinct(key) {
    const vals = state.allData.filter(r => r.상태 !== "moving").map(r => String(r[key] ?? "").trim()).filter(Boolean);
    return [...new Set(vals)].sort((a, b) => a.localeCompare(b, "ko"));
}

// pipeline/notify.py matches()와 같은 규칙 — 미리보기 건수용
function matches(rule, item) {
    if (rule.창고.length && !rule.창고.includes(item.창고)) return false;
    if (rule.상품명 && !norm(item.상품명).includes(norm(rule.상품명))) return false;
    if (rule.브랜드 && norm(item.브랜드) !== norm(rule.브랜드)) return false;
    if (rule.등급 && norm(item.등급) !== norm(rule.등급)) return false;
    if (rule.ESTNO && norm(item.ESTNO) !== norm(rule.ESTNO)) return false;
    return true;
}

function describe(rule) {
    const where = rule.창고.length ? rule.창고.join("·") : "전체 창고";
    const what = [rule.브랜드, rule.등급 ? gradeLabel(rule.등급) : (rule.브랜드 || rule.상품명) && "모든 등급", rule.상품명,
        rule.ESTNO && `(EST ${rule.ESTNO})`].filter(Boolean).join(" ") || "모든 상품";
    return `${where}에 ${what} 입고`;
}

// "2026-11-27T14:32:05" → 날짜 묶음 제목 "11월 27일 (목)" / 시각 "14:32"
const WEEKDAYS = "일월화수목금토";
function splitWhen(s) {
    const [d, t = ""] = String(s ?? "").split(/[T ]/);
    const [y, m, day] = d.split("-").map(Number);
    const wd = WEEKDAYS[new Date(y, m - 1, day).getDay()] ?? "";
    return { day: `${m}월 ${day}일 (${wd})`, time: t.slice(0, 5) };
}

// 받은 알림 — 날짜별로 묶고, 시각·창고·상품·입고 수량·현재 재고를 칸별로.
// 예전 알림(칸별 정보 없이 문장만 있는 것)은 상품 칸에 문장을 그대로 보여준다.
function inboxHtml(inbox) {
    lastInbox = new Map(inbox.data.map(n => [String(n.id), n]));
    if (!inbox.data.length) return `<tr><td colspan="6" class="notify-empty">받은 알림이 없습니다.</td></tr>`;
    let lastDay = "";
    return inbox.data.map(n => {
        const { day, time } = splitWhen(n.created_at);
        const dayRow = day !== lastDay ? `<tr class="notify-day-row"><td colspan="6">${esc(day)}</td></tr>` : "";
        lastDay = day;
        const product = n.상품명
            ? `<span class="nf-prod-name">${esc(n.상품명)}</span>
               <span class="nf-prod-meta">${[n.브랜드, n.등급 && gradeLabel(n.등급), n.ESTNO && `EST ${n.ESTNO}`].filter(Boolean).map(esc).join(" · ")}</span>`
            : esc(n.message);
        return `${dayRow}
        <tr class="notify-inbox-row${n.read_at ? "" : " notify-unread"}" data-nid="${n.id}" title="클릭하면 재고장에서 이 상품을 바로 예약">
            <td class="nf-col-time">${esc(time)}</td>
            <td class="nf-col-wh">${esc(n.창고)}</td>
            <td class="nf-wrap" title="${esc([n.상품명, n.브랜드, n.등급 && gradeLabel(n.등급), n.ESTNO && `EST ${n.ESTNO}`].filter(Boolean).join(" · "))}">${product}</td>
            <td class="nf-col-qty"><span class="nf-inc">+${esc(n.증가)}</span>박스</td>
            <td class="nf-col-qty">${esc(n.현재)}박스</td>
            <td class="nf-col-del">
                <button type="button" class="nf-read-btn" data-id="${n.id}" data-read="${n.read_at ? "0" : "1"}">${n.read_at ? "안읽음" : "읽음"}</button>
                <button type="button" class="nf-inbox-del-btn" data-id="${n.id}">삭제</button>
            </td>
        </tr>`;
    }).join("");
}

function rulesHtml(rules) {
    if (!rules.length) return `<tr><td colspan="6" class="notify-empty">예약된 알림이 없습니다.</td></tr>`;
    return rules.map(r => `
        <tr>
            <td class="nf-wrap">${esc(describe(r))}</td>
            <td class="nf-wrap">${esc(r.대상.join(", "))}</td>
            <td>입고 즉시</td>
            <td>매번</td>
            <td>사용 중</td>
            <td class="nf-col-del"><button type="button" class="nf-delete-btn" data-id="${esc(r.id)}">삭제</button></td>
        </tr>`).join("");
}

function formHtml() {
    const datalist = (id, key) => `<datalist id="${id}">${distinct(key).map(v =>
        `<option value="${esc(v)}"${key === "등급" && GRADE_NAMES[v] ? ` label="${esc(GRADE_NAMES[v])}"` : ""}>`).join("")}</datalist>`;
    const chips = (cls, values, checked = []) => values.map(v =>
        `<label class="nf-chip"><input type="checkbox" class="${cls}" value="${esc(v)}"${checked.includes(v) ? " checked" : ""}><span>${esc(v)}</span></label>`).join("");
    const me = userName();
    // 창고는 곤지암(자사, "곤"으로 시작) / 외부로 나눠서 같은 크기 칸에 정렬
    const whs = distinct("창고");
    const group = (title, values) => values.length ? `
        <div class="nf-group">
            <span class="nf-group-title">${title}</span>
            <div class="nf-chip-grid">${chips("nf-wh", values)}</div>
        </div>` : "";
    return `
        <div class="notify-form">
            <div class="nf-row">
                <span class="nf-label">조건</span>
                <div class="nf-inline">
                    <select class="nf-event"><option value="입고">새로 생기거나 수량이 늘면</option></select>
                    <span class="nf-label">받는 사람</span>
                    <div class="nf-chip-grid nf-to-grid">${chips("nf-to", teamNames(), [me])}</div>
                </div>
            </div>
            <div class="nf-row">
                <span class="nf-label">창고</span>
                <div class="nf-groups">
                    ${group("곤지암 창고", whs.filter(w => w.startsWith("곤")))}
                    ${group("외부 창고", whs.filter(w => !w.startsWith("곤")))}
                </div>
            </div>
            <div class="nf-row">
                <span class="nf-label">상품</span>
                <div class="nf-inputs">
                    <label>브랜드<input class="nf-input" data-field="브랜드" list="nf-brand-list" placeholder="예: EXCEL, 엑셀"></label>
                    <label>등급<input class="nf-input" data-field="등급" list="nf-grade-list" placeholder="비우면 전체 (예: PR)"></label>
                    <label>상품명<input class="nf-input" data-field="상품명" list="nf-name-list" placeholder="예: 냉장알목심"></label>
                    <label>ESTNO<input class="nf-input" data-field="ESTNO" list="nf-est-list" placeholder="비우면 전체"></label>
                </div>
                ${datalist("nf-brand-list", "브랜드")}${datalist("nf-grade-list", "등급")}${datalist("nf-name-list", "상품명")}${datalist("nf-est-list", "ESTNO")}
            </div>
            <p class="nf-hint">비워 둔 칸은 조건 없음(전체)입니다 — 등급·ESTNO를 비우면 구별 없이 모두 알림. 상품명은 일부만 써도 됩니다(예: "알목심").</p>
            <p class="nf-preview"></p>
            <div class="nf-actions">
                <button type="button" class="nf-cancel-btn">취소</button>
                <button type="button" class="nf-save-btn">저장</button>
            </div>
        </div>`;
}

function readForm(view) {
    const rule = {
        창고: [...view.querySelectorAll(".nf-wh:checked")].map(el => el.value),
        대상: [...view.querySelectorAll(".nf-to:checked")].map(el => el.value),
    };
    COND_FIELDS.forEach(f => { rule[f] = view.querySelector(`.nf-input[data-field="${f}"]`)?.value.trim() || ""; });
    if (rule.등급) rule.등급 = toGradeCode(rule.등급);
    // 브랜드 한글 표기(엑셀, 퇴니스 등)는 영문 브랜드값으로 — 재고장 검색과 같은 별칭 표 사용
    if (BRAND_ALIASES[rule.브랜드]) rule.브랜드 = BRAND_ALIASES[rule.브랜드];
    return rule;
}

function updatePreview(view) {
    const el = view.querySelector(".nf-preview");
    if (!el) return;
    const rule = readForm(view);
    const hit = state.allData.filter(r => r.상태 !== "moving" && matches(rule, r));
    const boxes = hit.reduce((s, r) => s + (Number(r.재고) || 0), 0);
    el.textContent = `미리보기: ${describe(rule)} 시 → ${rule.대상.join(", ") || "(받는 사람 없음)"} · 지금 조건에 맞는 재고 ${hit.length}건(${boxes}박스)`;
}

async function render(view) {
    const user = userName();
    if (!user) { view.innerHTML = `<p class="notify-empty">로그인 후 사용할 수 있습니다.</p>`; return; }
    let rules = [], inbox = { unread: 0, data: [] };
    try {
        [{ data: rules }, inbox] = await Promise.all([
            apiFetch(`/api/notify/rules?user=${encodeURIComponent(user)}`),
            apiFetch(`/api/notify/inbox?user=${encodeURIComponent(user)}`),
        ]);
    } catch (e) {
        view.innerHTML = `<p class="notify-empty">알림 정보를 불러오지 못했습니다.</p>`;
        return;
    }
    view.innerHTML = `
        <div class="notify-layout">
        <div class="notify-left">
        <section>
        <h3 class="crawling-section-title notify-inbox-title">받은 알림${inbox.unread ? ` <span class="notify-unread-count">새 알림 ${inbox.unread}</span>
            <button type="button" class="nf-read-all-btn">모두 읽음</button>` : ""}</h3>
        <div class="crawling-totals-wrap notify-scroll">
        <table class="reservations-table notify-list-table notify-inbox-table">
            <thead><tr><th>입고 시각</th><th>창고</th><th>상품</th><th>입고 수량</th><th>현재 재고</th><th></th></tr></thead>
            <tbody>${inboxHtml(inbox)}</tbody>
        </table>
        </div>
        </section>
        <section>
        <h3 class="crawling-section-title">알림 예약 목록</h3>
        <div class="crawling-totals-wrap notify-scroll">
        <table class="reservations-table notify-list-table">
            <thead><tr><th>알림 내용</th><th>받는 사람</th><th>알림 시각</th><th>반복</th><th>상태</th><th></th></tr></thead>
            <tbody>${rulesHtml(rules)}</tbody>
        </table>
        </div>
        </section>
        </div>
        <div class="notify-right">
        <h3 class="crawling-section-title">알림 설정하기</h3>
        <div class="notify-setup">
            <p class="notify-setup-desc">어느 창고에 어떤 상품이 들어오면 누구에게 알림을 보낼지 정합니다.</p>
            <button type="button" class="notify-new-btn">＋ 새 알림 설정</button>
        </div>
        <div class="notify-form-wrap"></div>
        </div>
        </div>
    `;
    // 읽음 처리는 알림별 "읽음"/"모두 읽음" 버튼으로(2026-11-27) — 화면을 연다고 자동으로 읽지 않음
    setBadge(inbox.unread);
}

function bind(view) {
    view.addEventListener("click", async (e) => {
        if (e.target.closest(".notify-new-btn")) {
            view.querySelector(".notify-form-wrap").innerHTML = formHtml();
            view.querySelector(".notify-setup").style.display = "none";
            updatePreview(view);
            return;
        }
        if (e.target.closest(".nf-cancel-btn")) { render(view); return; }
        if (e.target.closest(".nf-save-btn")) {
            const user = userName();
            if (!user) { showError("로그인 후 설정할 수 있습니다"); return; }
            const rule = readForm(view);
            if (!rule.창고.length && COND_FIELDS.every(f => !rule[f])) { showError("창고나 상품 조건을 하나 이상 정하세요"); return; }
            if (!rule.대상.length) { showError("받을 직원을 한 명 이상 고르세요"); return; }
            try {
                await apiFetch("/api/notify/rules", { method: "POST", body: JSON.stringify({ ...rule, 생성자: user }) });
            } catch (err) { showError(err.message || "저장하지 못했습니다"); return; }
            showToast("✓ 알림을 저장했습니다");
            render(view);
            return;
        }
        const user = userName();
        // 알림 행 클릭(버튼 제외) → 읽음 처리 후 재고장에서 바로 예약
        const row = e.target.closest(".notify-inbox-row");
        if (row && !e.target.closest("button") && navigateToItem) {
            const n = lastInbox.get(row.dataset.nid);
            if (!n) return;
            if (!n.read_at) apiFetch(`/api/notify/inbox/${n.id}/read`, { method: "POST", body: JSON.stringify({ user, read: true }) }).then(refreshNotifyBadge).catch(() => {});
            navigateToItem({ ...n, itemId: toStateId(n.item_key) });
            return;
        }
        const readBtn = e.target.closest(".nf-read-btn");
        if (readBtn) {
            try {
                await apiFetch(`/api/notify/inbox/${readBtn.dataset.id}/read`, { method: "POST", body: JSON.stringify({ user, read: readBtn.dataset.read === "1" }) });
            } catch (err) { showError(err.message || "바꾸지 못했습니다"); return; }
            render(view);
            return;
        }
        if (e.target.closest(".nf-read-all-btn")) {
            try {
                await apiFetch("/api/notify/inbox/read", { method: "POST", body: JSON.stringify({ user }) });
            } catch (err) { showError(err.message || "바꾸지 못했습니다"); return; }
            render(view);
            return;
        }
        const inboxDel = e.target.closest(".nf-inbox-del-btn");
        if (inboxDel) {
            if (!await showConfirm("이 받은 알림을 삭제할까요?")) return;
            try {
                await apiFetch(`/api/notify/inbox/${inboxDel.dataset.id}?user=${encodeURIComponent(user)}`, { method: "DELETE" });
            } catch (err) { showError(err.message || "삭제하지 못했습니다"); return; }
            render(view);
            return;
        }
        const del = e.target.closest(".nf-delete-btn");
        if (del) {
            if (!await showConfirm("이 알림을 삭제할까요?\n받는 사람 모두에게서 삭제됩니다.")) return;
            try {
                await apiFetch(`/api/notify/rules/${encodeURIComponent(del.dataset.id)}`, { method: "DELETE" });
            } catch (err) { showError(err.message || "삭제하지 못했습니다"); return; }
            render(view);
        }
    });
    view.addEventListener("input", () => updatePreview(view));
    view.addEventListener("change", () => updatePreview(view));
}

export function renderNotifyTab() {
    const view = document.getElementById("notify-view");
    if (!view) return;
    if (!view.dataset.bound) { bind(view); view.dataset.bound = "1"; }
    render(view);
}

// ── 종 배지 — 안 읽은 알림 수를 로그인(이름) 버튼과 종 버튼에 빨간 숫자로 ──
function setBadge(n) {
    for (const el of document.querySelectorAll(".login-btn, .notify-bell-btn")) {
        el.classList.toggle("has-alert", n > 0);
        el.dataset.alert = n > 0 ? String(n) : "";
    }
}

async function refreshNotifyBadge() {
    const user = userName();
    if (!user) { setBadge(0); return; }
    try {
        const r = await apiFetch(`/api/notify/inbox?user=${encodeURIComponent(user)}`);
        setBadge(r.unread);
    } catch {}
}

// 1분마다 안 읽은 알림 수 확인(로그인 안 했으면 배지 없음)
setTimeout(refreshNotifyBadge, 1500);
setInterval(refreshNotifyBadge, 60000);
