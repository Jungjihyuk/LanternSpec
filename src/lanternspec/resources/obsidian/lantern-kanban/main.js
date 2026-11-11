// Draws a `lantern-kanban` code block: the JSON that `lantern report` writes (report/views.py).
// Which stage a work is at and what its tasks are is decided there. This file only draws them, and reads nothing else
// in the vault and writes nothing: stages move by the skills and their approvals, tasks are checked off by /l-build.
const { MarkdownRenderChild, Modal, Plugin } = require("obsidian");

const BEFORE = ["plan", "design", "tasks"]; // the stages shown under "not started"
const COLUMNS = [...BEFORE, "build", "done"];
const MS_PER_DAY = 86400000;

function make(parent, className, text) {
  const el = document.createElement("div");
  el.className = className;
  if (text !== undefined) el.textContent = text;
  parent.appendChild(el);
  return el;
}

const fill = (template, values) => template.replace(/\{(\w+)\}/g, (whole, key) => (key in values ? String(values[key]) : whole));

// "34분", "1시간 20분", "2일 3시간": the two largest units, in the report's language.
function duration(minutes, labels) {
  const unit = (key, n) => fill(labels[key], { n });
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const mins = Math.round(minutes % 60);
  const parts = days ? [unit("days", days), hours && unit("hours", hours)] : hours ? [unit("hours", hours), mins && unit("minutes", mins)] : [unit("minutes", mins)];
  return parts.filter(Boolean).join(" ");
}

const dayNumber = (text) => {
  const [y, m, d] = text.slice(0, 10).split("-").map(Number);
  return Date.UTC(y, m - 1, d) / MS_PER_DAY;
};
const dateLabel = (text, labels) => fill(labels.date, { m: Number(text.slice(5, 7)), d: Number(text.slice(8, 10)) });

// What a work waits on, if anything: a person (approval or a check) or an answer.
function flags(work, labels) {
  const out = [];
  if (work.unknown) out.push(["ask", fill(labels.unknown, { n: work.unknown })]);
  if (work.stage === "design" && !work.approved) out.push(["wait", labels.design_wait]);
  if (work.person) out.push(["wait", fill(labels.person, { n: work.person })]);
  return out;
}

const counts = (work) => ({
  done: work.tasks.filter((t) => t.state === "done").length,
  blocked: work.tasks.filter((t) => t.state === "blocked").length,
  doing: work.tasks.find((t) => t.state === "doing"),
});

class TaskWindow extends Modal {
  constructor(app, board, work) {
    super(app);
    this.board = board;
    this.work = work;
  }

  onOpen() {
    const { labels, stages } = this.board.data;
    const work = this.work;
    const stage = stages.find((s) => s.role === work.stage) || stages[0];
    this.modalEl.addClass("lk-window");
    const el = this.contentEl;
    el.empty();
    const head = make(el, `lk-window-head lk-stage-${work.stage}`);
    make(head, "lk-window-stage", stage.name);
    const title = make(head, "lk-window-title");
    make(title, "lk-id", work.id);
    title.appendText(work.name);
    const facts = make(head, "lk-window-facts");
    const fact = (label, value) => {
      const span = make(facts, "");
      span.appendText(`${label} `);
      span.createEl("b", { text: value });
    };
    if (work.approved) fact(labels.approved, dateLabel(work.approved, labels));
    if (work.tasks.length) {
      const c = counts(work);
      fact("", `${fill(labels.progress, { done: c.done, total: work.tasks.length })} · ${fill(labels.blocked, { n: c.blocked })}`);
    }
    const next = this.board.nextStep(work);
    if (next) fact(labels.next, next);
    const docs = make(head, "lk-window-docs");
    for (const [role, path] of Object.entries(work.docs)) {
      const link = docs.createEl("a", { text: labels.docs[role] || role, href: "#" });
      link.addEventListener("click", (event) => {
        event.preventDefault();
        this.close();
        this.app.workspace.openLinkText(path, this.board.sourcePath);
      });
    }
    const body = make(el, "lk-window-body");
    if (!work.tasks.length) {
      make(body, "lk-window-empty", labels.empty);
    } else {
      const table = body.createEl("table");
      const header = table.createEl("tr");
      for (const name of [labels.task, labels.state, labels.size, labels.after, labels.criteria, labels.by]) header.createEl("th", { text: name });
      const stateName = { todo: labels.todo, blocked: labels.state_blocked, doing: labels.state_doing, done: labels.state_done };
      for (const task of work.tasks) {
        const row = table.createEl("tr");
        // the name only; what follows its dash is the detail, kept for pointing at it
        const [name] = task.title.split(" — ");
        row.createEl("td", { text: `${task.id} ${name}`, cls: "lk-t" }).title = task.title;
        const state = row.createEl("td").createSpan({ cls: `lk-state lk-state-${task.state}` });
        state.createEl("i");
        state.appendText(stateName[task.state]);
        const size = row.createEl("td", { cls: "lk-nw" });
        if (task.size) size.createSpan({ cls: "lk-size", text: task.size });
        row.createEl("td", { text: task.after.join(", "), cls: "lk-mono lk-nw" });
        row.createEl("td", { text: task.criteria.join(", "), cls: "lk-mono" });
        // who did it, colored as people · people with AI · AI; the exact names as written
        const by = row.createEl("td", { cls: "lk-by" });
        if (task.who) by.createSpan({ cls: `lk-who-dot lk-who-${task.who}` });
        by.appendText((task.by || []).join(", "));
      }
    }
    make(body, "lk-window-foot", labels.read_only);
  }

  onClose() {
    this.contentEl.empty();
  }
}

class Board extends MarkdownRenderChild {
  constructor(el, data, app, sourcePath) {
    super(el);
    this.el = el;
    this.data = data;
    this.app = app;
    this.sourcePath = sourcePath;
    this.showOlder = false;
    this.showHold = false;
  }

  onload() {
    this.draw();
  }

  nextStep(work) {
    const { labels } = this.data;
    if (work.stage === "plan") return `/l-design ${work.id}`;
    if (work.stage === "design") return work.approved ? `/l-task ${work.id}` : labels.design_wait;
    if (work.stage === "tasks" || work.stage === "build") return `/l-build ${work.id}`;
    return "";
  }

  open(work) {
    new TaskWindow(this.app, this, work).open();
  }

  card(parent, work) {
    const card = make(parent, `lk-card lk-stage-${work.stage}`);
    card.addEventListener("click", () => this.open(work));
    make(card, "lk-id", work.id);
    make(card, "lk-title", work.name);
    const { labels } = this.data;
    if (work.tasks.length) {
      // one segment per task: done · doing · blocked · to do
      const segs = make(card, "lk-segs");
      for (const task of work.tasks) make(segs, `lk-seg-${task.state}${task.who ? ` lk-who-${task.who}` : ""}`);
      const c = counts(work);
      const meta = make(card, "lk-meta");
      const parts = [fill(labels.progress, { done: c.done, total: work.tasks.length })];
      if (c.blocked) parts.push(fill(labels.blocked, { n: c.blocked }));
      if (c.doing) parts.push(fill(labels.now, { id: c.doing.id }));
      meta.textContent = parts.join(" · ");
      if (c.doing) card.addClass("lk-now");
    }
    for (const [kind, text] of flags(work, labels)) make(card, `lk-flag lk-flag-${kind}`, text);
  }

  doneList(parent, works) {
    const { labels } = this.data;
    const list = make(parent, "lk-done");
    const longest = Math.max(1, ...works.map((w) => w.worked));
    let day = "";
    for (const work of works) {
      if (work.finished !== day) {
        day = work.finished;
        make(list, "lk-day", day ? dateLabel(day, labels) : "");
      }
      const row = make(list, "lk-row");
      row.addEventListener("click", () => this.open(work));
      make(row, "lk-id", work.id);
      make(row, "lk-row-title", work.name).title = work.name;
      const time = make(row, "lk-time", work.worked ? duration(work.worked, labels) : "");
      // time worked, as a short bar against the longest in the list
      if (work.worked) make(time, `lk-time-bar${work.who ? ` lk-who-${work.who}` : ""}`).style.width = `${Math.max(4, (work.worked / longest) * 48)}px`;
    }
  }

  draw() {
    const { labels, stages, works } = this.data;
    const today = dayNumber(this.data.today);
    const byStage = (role) => works.filter((w) => w.stage === role);
    const done = byStage("done").sort((a, b) => (a.finished < b.finished ? 1 : -1));
    const recent = done.filter((w) => w.finished && today - dayNumber(w.finished) < this.data.recent_days);
    const older = done.filter((w) => !recent.includes(w));
    const active = works.filter((w) => BEFORE.includes(w.stage) || w.stage === "build");
    const waiting = active.filter((w) => flags(w, labels).some(([kind]) => kind === "wait")).length;

    const root = document.createElement("div");
    root.className = "lk-root";
    const top = make(root, "lk-top");
    const count = (label, n, cls = "") => {
      const span = make(top, cls);
      span.appendText(`${label} `);
      span.createEl("b", { text: String(n) });
    };
    count(labels.doing, active.length);
    count(labels.waiting, waiting, waiting ? "lk-top-wait" : "");
    count(labels.recent, recent.length);
    // the colors of who did the work, when any task says
    const whos = new Set(works.flatMap((w) => w.tasks.map((t) => t.who)).filter(Boolean));
    for (const who of ["human", "both", "ai"].filter((w) => whos.has(w))) {
      const key = make(top, "lk-top-who");
      make(key, `lk-who-dot lk-who-${who}`);
      key.appendText(labels[`who_${who}`]);
    }

    // the flow rail: the five steps as one line, with the three groups named on it
    const rail = make(root, "lk-rail lk-grid");
    for (const role of COLUMNS) {
      const dot = make(rail, `lk-rail-step lk-stage-${role}`);
      const group = role === "plan" ? labels.before : role === "build" ? labels.doing : role === "done" ? labels.ended : "";
      if (group) dot.createEl("em", { text: group });
    }

    const board = make(root, "lk-board lk-grid");
    for (const role of COLUMNS) {
      const stage = stages.find((s) => s.role === role);
      const col = make(board, `lk-col lk-stage-${role}`);
      const head = make(col, "lk-col-head");
      make(head, "lk-ico", stage.icon);
      make(head, "lk-col-name", stage.name);
      make(head, "lk-n", String(role === "done" ? recent.length : byStage(role).length));
      make(col, "lk-next", role === "done" ? labels.done_hint : `→ ${labels[`next_${role}`]}`);
      if (role === "done") {
        if (recent.length) this.doneList(col, recent);
        if (older.length) {
          const more = make(col, "lk-more", this.showOlder ? "" : fill(labels.older, { n: older.length }));
          more.addEventListener("click", () => {
            this.showOlder = !this.showOlder;
            this.draw();
          });
          if (this.showOlder) this.doneList(col, older);
        }
        const hold = byStage("on_hold");
        const holdStage = stages.find((s) => s.role === "on_hold");
        const holdEl = make(col, "lk-hold", `${holdStage.icon} ${holdStage.name} ${hold.length}${hold.length ? (this.showHold ? " ▾" : " ▸") : ""}`);
        if (hold.length) {
          holdEl.addEventListener("click", () => {
            this.showHold = !this.showHold;
            this.draw();
          });
          if (this.showHold) for (const work of hold) this.card(col, work);
        }
        continue;
      }
      const cards = byStage(role);
      if (!cards.length) make(col, "lk-empty", labels.empty);
      for (const work of cards) this.card(col, work);
    }
    this.el.replaceChildren(root);
  }
}

module.exports = class LanternKanban extends Plugin {
  onload() {
    this.registerMarkdownCodeBlockProcessor("lantern-kanban", (source, el, ctx) => {
      let data;
      try {
        data = JSON.parse(source);
      } catch (error) {
        make(el, "lk-error", `Lantern Kanban: ${error.message}`);
        return;
      }
      ctx.addChild(new Board(el, data, this.app, ctx.sourcePath));
    });
  }
};
