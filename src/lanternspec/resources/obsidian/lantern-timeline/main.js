// Draws a `lantern-timeline` code block: the JSON that `lantern report` writes (report/views.py).
// Which dates a task gets is decided there; this file only draws them, and changes nothing in the vault.
const { Plugin } = require("obsidian");

const DAY_WIDTH = 28;
const NAME_WIDTH = 300;
const MS_PER_DAY = 86400000;

// Whole days only, counted in UTC so daylight saving never shifts a bar.
const dayNumber = (text) => {
  const [y, m, d] = text.slice(0, 10).split("-").map(Number);
  return Date.UTC(y, m - 1, d) / MS_PER_DAY;
};
const dateOf = (day) => new Date(day * MS_PER_DAY);
const todayNumber = () => {
  const now = new Date();
  return Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) / MS_PER_DAY;
};

function make(parent, className, text) {
  const el = document.createElement("div");
  el.className = className;
  if (text !== undefined) el.textContent = text;
  parent.appendChild(el);
  return el;
}

function range(data, today) {
  const days = [today];
  for (const work of data.works) {
    if (work.idea) days.push(dayNumber(work.idea.date));
    if (work.created) days.push(dayNumber(work.created));
    for (const task of work.tasks) days.push(dayNumber(task.start), dayNumber(task.end));
  }
  return { first: Math.min(...days) - 2, last: Math.max(today + 14, Math.max(...days) + 2) };
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

function drawWork(body, work, first, labels, open) {
  const done = work.tasks.filter((t) => t.state === "done").length;
  const row = make(body, "lt-row lt-work");
  const name = make(row, "lt-name");
  const fold = make(name, "lt-fold");
  make(name, "lt-work-name", `${work.id} ${work.name}`).title = `${work.id} ${work.name}`;
  make(name, "lt-count", work.tasks.length ? `${done}/${work.tasks.length}` : "");
  const track = make(row, "lt-track");

  if (work.tasks.length) {
    const from = Math.min(...work.tasks.map((t) => dayNumber(t.start)));
    const to = Math.max(...work.tasks.map((t) => dayNumber(t.end)));
    place(make(track, "lt-bar lt-summary"), from, to, first);
  }
  for (const [date, label] of [
    [work.idea && work.idea.date, work.idea && work.idea.id],
    [work.created, labels.plan],
  ]) {
    if (!date) continue;
    const mark = make(track, "lt-mark");
    mark.style.left = `${(dayNumber(date) - first) * DAY_WIDTH + DAY_WIDTH / 2 - 5}px`;
    mark.title = `${label} · ${date}`;
  }

  const rows = work.tasks.map((task) => {
    const line = make(body, "lt-row lt-task");
    const cell = make(line, "lt-name");
    const link = make(cell, "lt-task-name", `${task.id} ${task.title}`);
    link.title = `${task.id} ${task.title}`;
    link.dataset.file = work.file;
    const bar = make(make(line, "lt-track"), `lt-bar lt-${task.state} lt-${task.basis}`, task.id);
    place(bar, dayNumber(task.start), dayNumber(task.end), first);
    bar.title = `${task.id} ${task.title}\n${task.start} → ${task.end}\n${labels[task.state]} · ${labels[task.basis]}`;
    return line;
  });

  const set = (isOpen) => {
    fold.textContent = work.tasks.length ? (isOpen ? "▾" : "▸") : "";
    for (const line of rows) line.style.display = isOpen ? "" : "none";
  };
  let isOpen = open;
  set(isOpen);
  name.addEventListener("click", (event) => {
    if (event.target.classList.contains("lt-task-name")) return;
    isOpen = !isOpen;
    set(isOpen);
  });
}

function render(source, el, openFile) {
  let data;
  try {
    data = JSON.parse(source);
  } catch (error) {
    make(el, "lt-error", `Lantern Timeline: ${error.message}`);
    return;
  }
  const today = todayNumber();
  const { first, last } = range(data, today);
  const root = make(el, "lt-root");
  const legend = make(root, "lt-legend");
  for (const [cls, key] of [["done lt-actual", "done"], ["doing lt-actual", "doing"], ["todo lt-planned", "todo"], ["todo lt-estimated", "estimated"]]) {
    const item = make(legend, "lt-legend-item");
    make(item, `lt-swatch lt-bar lt-${cls}`);
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
  // works in progress start open; when all are finished, the latest one with tasks does
  const unfinished = (work) => work.tasks.some((t) => t.state !== "done");
  const latest = [...data.works].reverse().find((w) => w.tasks.length);
  const someOpen = data.works.some(unfinished);
  for (const work of data.works) {
    drawWork(body, work, first, data.labels, someOpen ? unfinished(work) : work === latest);
  }
  if (today >= first && today <= last) {
    make(body, "lt-today").style.left = `${NAME_WIDTH + (today - first) * DAY_WIDTH + DAY_WIDTH / 2}px`;
  }
  body.addEventListener("click", (event) => {
    if (event.target.classList.contains("lt-task-name")) openFile(event.target.dataset.file);
  });
  requestAnimationFrame(() => {
    const visible = Math.max(scroller.clientWidth - NAME_WIDTH, 0);
    scroller.scrollLeft = (today - first) * DAY_WIDTH - visible / 2;
  });
}

module.exports = class LanternTimeline extends Plugin {
  onload() {
    this.registerMarkdownCodeBlockProcessor("lantern-timeline", (source, el, ctx) => {
      render(source, el, (file) => this.app.workspace.openLinkText(file, ctx.sourcePath));
    });
  }
};
