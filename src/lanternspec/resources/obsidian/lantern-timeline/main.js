// Draws a `lantern-timeline` code block: the JSON that `lantern report` writes (report/views.py).
// Which dates a task gets is decided there. This file draws them, keeps them in step with the task's line in the tasks file,
// and changes only one thing in the vault: dragging a task that has not started writes its planned dates on that line.
const { MarkdownRenderChild, Notice, Plugin, TFile } = require("obsidian");

const DAY_WIDTH = 28;
const NAME_WIDTH = 300;
const HEADER_HEIGHT = 48;
const ROW_HEIGHT = 28;
const MS_PER_DAY = 86400000;
// The task line's format (core/taskfile.py) and the rule for its state (report/views.py), read here again to follow the file at once.
const TASK_LINE = /^\s*- \[( |x|X)\] (W-\d{3,}-T\d{2,})\b/;
const ATTR = /\[([^\[\]:]+?)::\s*([^\[\]]*?)\s*\]/g;
const DATE = /^\d{4}-\d{2}-\d{2}/;

// Whole days only, counted in UTC so daylight saving never shifts a bar.
const dayNumber = (text) => {
  const [y, m, d] = text.slice(0, 10).split("-").map(Number);
  return Date.UTC(y, m - 1, d) / MS_PER_DAY;
};
const dateOf = (day) => new Date(day * MS_PER_DAY);
const dateText = (day) => dateOf(day).toISOString().slice(0, 10);
const todayNumber = () => {
  const now = new Date();
  return Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) / MS_PER_DAY;
};
// An estimated end is the start of the next task; every other end is a day the task still takes.
const barDays = (task) => task.dragged || [dayNumber(task.start), dayNumber(task.end) - (task.basis === "estimated" ? 1 : 0)];

function readLine(line, fields) {
  const attrs = {};
  for (const [, name, value] of line.matchAll(ATTR)) attrs[name] = value;
  const start = attrs[fields.start_plan];
  const due = attrs[fields.due_plan];
  const planned = !attrs[fields.start] && DATE.test(start || "") && DATE.test(due || "") && dayNumber(start) <= dayNumber(due);
  return {
    state: !/^\s*- \[ \]/.test(line) ? "done" : attrs[fields.start] ? "doing" : "todo",
    planned: planned ? { start, due } : null,
  };
}

function followFile(work, text, fields) {
  const lines = new Map();
  for (const line of text.split("\n")) {
    const task = line.match(TASK_LINE);
    if (task) lines.set(task[2], readLine(line, fields));
  }
  for (const task of work.tasks) {
    const line = lines.get(`${work.id}-${task.id}`);
    if (!line) continue;
    task.state = line.state;
    if (line.planned) Object.assign(task, { start: line.planned.start, end: line.planned.due, basis: "planned" });
  }
}

function setAttr(line, name, value, unknown) {
  let found = false;
  const changed = line.replace(ATTR, (whole, key) => {
    if (key !== name || found) return whole;
    found = true;
    return `[${name}:: ${value}]`;
  });
  if (found) return changed;
  const base = line.trimEnd();
  // a trailing "needs answer" marker stays at the very end
  if (base.endsWith(unknown)) return `${base.slice(0, -unknown.length).trimEnd()} [${name}:: ${value}] ${unknown}`;
  return `${base} [${name}:: ${value}]`;
}

// The file with the task's planned dates, or null when the task has started or its line is gone.
function withPlannedDates(text, id, start, due, fields) {
  const lines = text.split("\n");
  const at = lines.findIndex((line) => (line.match(TASK_LINE) || [])[2] === id);
  if (at < 0 || readLine(lines[at], fields).state !== "todo") return null;
  lines[at] = setAttr(setAttr(lines[at], fields.start_plan, start, fields.unknown), fields.due_plan, due, fields.unknown);
  return lines.join("\n").replace(/^(---\n(?:(?!---\n)[\s\S])*?\nupdated:[ \t]*)[^\n]*/, (_, before) => before + dateText(todayNumber()));
}

function dragged(mode, from, to, days, first, last) {
  if (mode === "start") return [Math.max(first, Math.min(from + days, to)), to];
  if (mode === "end") return [from, Math.min(last, Math.max(to + days, from))];
  const moved = Math.max(first - from, Math.min(days, last - to));
  return [from + moved, to + moved];
}

function make(parent, className, text) {
  const el = document.createElement("div");
  el.className = className;
  if (text !== undefined) el.textContent = text;
  parent.appendChild(el);
  return el;
}

function statesIn(text, startField) {
  const states = {};
  for (const line of text.split("\n")) {
    const task = line.match(TASK_LINE);
    if (!task) continue;
    const started = [...line.matchAll(ATTR)].some(([, name, value]) => name === startField && value);
    states[task[2]] = task[1] !== " " ? "done" : started ? "doing" : "todo";
  }
  return states;
}

function range(data, today) {
  const days = [today];
  for (const work of data.works) {
    if (work.idea) days.push(dayNumber(work.idea.date));
    if (work.created) days.push(dayNumber(work.created));
    for (const task of work.tasks) days.push(...barDays(task));
  }
  // room to drag into
  return { first: Math.min(...days) - 7, last: Math.max(today + 30, Math.max(...days) + 14) };
}

function place(bar, from, to, first) {
  bar.style.left = `${(from - first) * DAY_WIDTH + 2}px`;
  bar.style.width = `${(to - from + 1) * DAY_WIDTH - 4}px`;
}

function drawHeader(body, first, last, today) {
  const months = make(body, "lt-row lt-months");
  make(months, "lt-name");
  const monthTrack = make(months, "lt-track");
  const days = make(body, "lt-row lt-days");
  make(days, "lt-name");
  const dayTrack = make(days, "lt-track");
  let monthStart = first;
  for (let day = first; day <= last; day++) {
    const date = dateOf(day);
    const cell = make(dayTrack, "lt-day", String(date.getUTCDate()));
    if ([0, 6].includes(date.getUTCDay())) cell.classList.add("lt-weekend");
    if (day === today) cell.classList.add("lt-today-cell");
    const next = dateOf(day + 1);
    if (day === last || next.getUTCMonth() !== date.getUTCMonth()) {
      const label = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
      make(monthTrack, "lt-month", label).style.width = `${(day - monthStart + 1) * DAY_WIDTH}px`;
      monthStart = day + 1;
    }
  }
}

function drawArrows(svg, shown, first) {
  svg.replaceChildren();
  const add = (d, className) => {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("class", className);
    svg.appendChild(path);
  };
  const rows = new Map(shown.map((task, row) => [task.fullId, { task, y: HEADER_HEIGHT + row * ROW_HEIGHT + ROW_HEIGHT / 2 }]));
  for (const [, { task, y }] of rows) {
    for (const id of task.after || []) {
      const before = rows.get(id);
      if (!before) continue;
      const beforeLast = barDays(before.task)[1];
      const from = barDays(task)[0];
      const x1 = (beforeLast - first + 1) * DAY_WIDTH - 2;
      const x2 = (from - first) * DAY_WIDTH + 2;
      const middle = y - Math.sign(y - before.y) * (ROW_HEIGHT / 2);
      const route = x2 >= x1 + 12 ? `H${(x1 + x2) / 2}V${y}` : `h5V${middle}H${x2 - 7}V${y}`;
      // what already happened can't be fixed, so only a task still to come is flagged
      const cls = task.state === "todo" && from < beforeLast ? "lt-arrow lt-arrow-late" : "lt-arrow";
      add(`M${x1} ${before.y}${route}H${x2 - 4}`, cls);
      add(`M${x2} ${y}l-5 -3v6z`, `${cls} lt-arrow-head`);
    }
  }
}

class Timeline extends MarkdownRenderChild {
  constructor(el, data, app, sourcePath) {
    super(el);
    this.el = el;
    this.data = data;
    this.app = app;
    this.sourcePath = sourcePath;
    this.folds = new Map();
    this.files = new Map(data.works.map((work) => [work.file, work]));
    for (const work of data.works) for (const task of work.tasks) task.fullId = `${work.id}-${task.id}`;
    // works in progress start open; when all are finished, the latest one with tasks does
    const unfinished = (work) => work.tasks.some((t) => t.state !== "done");
    const latest = [...data.works].reverse().find((w) => w.tasks.length);
    const someOpen = data.works.some(unfinished);
    for (const work of data.works) this.folds.set(work.id, someOpen ? unfinished(work) : work === latest);
  }

  async onload() {
    this.draw();
    if (!this.data.fields) return; // a report written by an older version says nothing about how to read a task line
    this.registerEvent(
      this.app.vault.on("modify", (file) => {
        if (this.files.has(file.path)) this.follow(file).then(() => this.draw());
      }),
    );
    const files = [...this.files.keys()].map((path) => this.app.vault.getAbstractFileByPath(path));
    await Promise.all(files.filter((file) => file instanceof TFile).map((file) => this.follow(file)));
    this.draw();
  }

  async follow(file) {
    followFile(this.files.get(file.path), await this.app.vault.cachedRead(file), this.data.fields);
  }

  async save(work, task, [from, to]) {
    const before = { start: task.start, end: task.end, basis: task.basis };
    Object.assign(task, { start: dateText(from), end: dateText(to), basis: "planned" });
    this.draw();
    const file = this.app.vault.getAbstractFileByPath(work.file);
    let saved = false;
    if (file instanceof TFile) {
      await this.app.vault.process(file, (text) => {
        const changed = withPlannedDates(text, task.fullId, task.start, task.end, this.data.fields);
        saved = changed !== null;
        return saved ? changed : text;
      });
    }
    if (saved) return;
    Object.assign(task, before);
    new Notice(this.data.labels.not_saved);
    this.draw();
  }

  startDrag(event, work, task, bar, mode) {
    event.preventDefault();
    event.stopPropagation();
    bar.setPointerCapture(event.pointerId);
    const [from, to] = barDays(task);
    const { first, last } = this.days;
    const tip = make(bar.parentElement, "lt-tip");
    this.dragging = true;
    const show = (days) => {
      task.dragged = dragged(mode, from, to, days, first, last);
      place(bar, ...task.dragged, first);
      tip.textContent = `${dateText(task.dragged[0])} → ${dateText(task.dragged[1])}`;
      tip.style.left = `${(task.dragged[1] - first + 1) * DAY_WIDTH + 4}px`;
      this.arrows();
    };
    const onMove = (e) => show(Math.round((e.clientX - event.clientX) / DAY_WIDTH));
    const stop = (e) => {
      bar.removeEventListener("pointermove", onMove);
      bar.removeEventListener("pointerup", stop);
      bar.removeEventListener("pointercancel", stop);
      tip.remove();
      this.dragging = false;
      const moved = task.dragged;
      delete task.dragged;
      const changed = e.type === "pointerup" && moved && (moved[0] !== from || moved[1] !== to);
      if (changed) this.save(work, task, moved).catch((error) => new Notice(`Lantern Timeline: ${error.message}`));
      else this.draw();
    };
    bar.addEventListener("pointermove", onMove);
    bar.addEventListener("pointerup", stop);
    bar.addEventListener("pointercancel", stop);
    show(0);
  }

  drawWork(body, work, first) {
    const labels = this.data.labels;
    const row = make(body, "lt-row lt-work");
    const name = make(row, "lt-name");
    const isOpen = this.folds.get(work.id);
    make(name, "lt-fold", work.tasks.length ? (isOpen ? "▾" : "▸") : "");
    make(name, "lt-work-name", `${work.id} ${work.name}`).title = `${work.id} ${work.name}`;
    const done = work.tasks.filter((t) => t.state === "done").length;
    make(name, "lt-count", work.tasks.length ? `${done}/${work.tasks.length}` : "");
    name.addEventListener("click", () => {
      this.folds.set(work.id, !isOpen);
      this.draw();
    });
    const track = make(row, "lt-track");

    if (work.tasks.length) {
      const days = work.tasks.map(barDays);
      place(make(track, "lt-bar lt-summary"), Math.min(...days.map((d) => d[0])), Math.max(...days.map((d) => d[1])), first);
    }
    for (const [date, label, cls] of [
      [work.idea && work.idea.date, work.idea && `${work.idea.id} · ${labels.idea}`, "lt-mark-idea"],
      [work.created, labels.plan, "lt-mark-plan"],
    ]) {
      if (!date) continue;
      const mark = make(track, `lt-mark ${cls}`);
      mark.style.left = `${(dayNumber(date) - first) * DAY_WIDTH + DAY_WIDTH / 2 - 5}px`;
      mark.title = `${label} · ${date}`;
    }
    if (!isOpen) return [];

    for (const task of work.tasks) {
      const line = make(body, "lt-row lt-task");
      const link = make(make(line, "lt-name"), "lt-task-name", `${task.id} ${task.title}`);
      link.title = `${task.id} ${task.title}`;
      link.addEventListener("click", () => this.app.workspace.openLinkText(work.file, this.sourcePath));
      const bar = make(make(line, "lt-track"), `lt-bar lt-${task.state} lt-${task.basis}`, task.id);
      const [from, to] = barDays(task);
      place(bar, from, to, first);
      const end = task.basis === "actual" ? task.end : dateText(to);
      bar.title = `${task.id} ${task.title}\n${task.start} → ${end}\n${labels[task.state]} · ${labels[task.basis]}`;
      // only a task that has not started can move: actual times stay as they happened
      if (task.state !== "todo" || !this.data.fields) continue;
      bar.classList.add("lt-movable");
      make(bar, "lt-handle lt-handle-start").dataset.mode = "start";
      make(bar, "lt-handle lt-handle-end").dataset.mode = "end";
      bar.addEventListener("pointerdown", (event) => this.startDrag(event, work, task, bar, event.target.dataset.mode || "move"));
    }
    return work.tasks;
  }

  arrows() {
    drawArrows(this.svg, this.shown, this.days.first);
  }

  draw() {
    if (this.dragging) return;
    const old = this.scroller;
    const scrollDay = old && this.days.first + old.scrollLeft / DAY_WIDTH;
    const scrollTop = old ? old.scrollTop : 0;
    const today = todayNumber();
    const data = this.data;
    const { first, last } = (this.days = range(data, today));
    const root = document.createElement("div");
    root.className = "lt-root";
    const legend = make(root, "lt-legend");
    for (const [cls, key] of [
      ["lt-swatch lt-bar lt-done lt-actual", "done"],
      ["lt-swatch lt-bar lt-doing lt-actual", "doing"],
      ["lt-swatch lt-bar lt-todo lt-planned", "todo"],
      ["lt-swatch lt-bar lt-todo lt-estimated", "estimated"],
      ["lt-swatch lt-bar lt-summary", "span"],
      ["lt-mark lt-mark-idea", "idea"],
      ["lt-mark lt-mark-plan", "plan"],
      ["lt-swatch lt-line", "after"],
      ["lt-swatch lt-line lt-line-late", "late"],
    ]) {
      if (!data.labels[key]) continue; // a report written by an older version has fewer labels
      const item = make(legend, "lt-legend-item");
      make(item, cls);
      make(item, "", data.labels[key]);
    }

    const scroller = make(root, "lt-scroller");
    const body = make(scroller, "lt-body");
    const trackWidth = (last - first + 1) * DAY_WIDTH;
    body.style.width = `${NAME_WIDTH + trackWidth}px`;
    body.style.setProperty("--lt-name-width", `${NAME_WIDTH}px`);
    body.style.setProperty("--lt-day-width", `${DAY_WIDTH}px`);
    body.style.setProperty("--lt-track-width", `${trackWidth}px`);
    // the week tile starts with its shaded days, so it is shifted to start on a Saturday
    const saturday = (6 - dateOf(first).getUTCDay() + 7) % 7;
    body.style.setProperty("--lt-weekend-shift", `${saturday * DAY_WIDTH}px`);

    drawHeader(body, first, last, today);
    this.shown = [];
    for (const work of data.works) {
      this.shown.push({}, ...this.drawWork(body, work, first)); // the work's own row, then its open tasks
    }
    this.svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    this.svg.setAttribute("class", "lt-arrows");
    this.svg.setAttribute("width", trackWidth);
    this.svg.setAttribute("height", HEADER_HEIGHT + this.shown.length * ROW_HEIGHT);
    this.svg.style.left = `${NAME_WIDTH}px`;
    body.appendChild(this.svg);
    this.arrows();
    make(body, "lt-today").style.left = `${NAME_WIDTH + (today - first) * DAY_WIDTH + DAY_WIDTH / 2}px`;

    this.el.replaceChildren(root);
    this.scroller = scroller;
    const scroll = () => {
      const visible = Math.max(scroller.clientWidth - NAME_WIDTH, 0);
      scroller.scrollLeft = old ? (scrollDay - first) * DAY_WIDTH : (today - first) * DAY_WIDTH - visible / 2;
      scroller.scrollTop = scrollTop;
    };
    scroll();
    requestAnimationFrame(scroll);
  }
}

module.exports = class LanternTimeline extends Plugin {
  onload() {
    this.registerMarkdownCodeBlockProcessor("lantern-timeline", (source, el, ctx) => {
      let data;
      try {
        data = JSON.parse(source);
      } catch (error) {
        make(el, "lt-error", `Lantern Timeline: ${error.message}`);
        return;
      }
      ctx.addChild(new Timeline(el, data, this.app, ctx.sourcePath));
    });
  }
};
