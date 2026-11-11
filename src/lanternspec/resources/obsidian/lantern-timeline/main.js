// Draws a `lantern-timeline` code block: the JSON that `lantern report` writes (report/views.py).
// Which dates a task gets is decided there. This file draws them, keeps them in step with the task's line in the tasks file,
// and changes only one thing in the vault: dragging a task that has not started writes its planned dates on that line.
const { MarkdownRenderChild, Notice, Plugin, TFile } = require("obsidian");

const DAY_WIDTH = 28;
const NAME_WIDTH = 210;
const HEADER_HEIGHT = 48;
const ROW_HEIGHT = 28;
const MS_PER_DAY = 86400000;
const MIN_PER_DAY = 1440;
// Work done in bursts gets columns finer than a day, so tasks an AI finishes in minutes still read as a staircase:
// the finest of these that lets the chart fit the note's width (else that lets each busy stretch fit),
// as long as the busy time adds up to no more than FINE_HOURS; else whole days.
const FINE_SLOTS = [5, 10, 30, 60];
const FINE_HOURS = 120;
// Time with no task at all is folded into a narrow strip that says how long it was:
// an hour or more on a finer chart, three days or more on a day chart.
const FOLD_MINUTES = 60;
const FOLD_DAYS = 3;
const FOLD_COLUMNS = 3;
const MIN_BAR = 6;
// Tasks with no date yet wait in a column on the right, off the time axis: a size says how much work, not when.
const TRAY_WIDTH = 132;
const TRAY_NARROW = 36; // when no open work has an undated task: a strip with the counts, widened by a click
// The task line's format (core/taskfile.py) and the rule for its state (report/views.py), read here again to follow the file at once.
const TASK_LINE = /^\s*- \[( |x|X)\] (W-\d{3,}-T\d{2,})\b/;
const ATTR = /\[([^\[\]:]+?)::\s*([^\[\]]*?)\s*\]/g;
const DATE = /^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$/; // a planned date, with or without a time

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
// Minutes counted the same way, so a task keeps the time of day it ran at.
const minuteOf = (text) => {
  const [, h, m] = text.match(/ (\d{2}):(\d{2})/) || [0, 0, 0];
  return dayNumber(text) * MIN_PER_DAY + Number(h) * 60 + Number(m);
};
const nowMinute = () => {
  const now = new Date();
  return todayNumber() * MIN_PER_DAY + now.getHours() * 60 + now.getMinutes();
};
// A planned date written with a time is that minute; one without a time is the whole day.
const hasTime = (text) => / \d{2}:\d{2}/.test(text || "");
const planStart = (text) => (hasTime(text) ? minuteOf(text) : dayNumber(text) * MIN_PER_DAY);
const planEnd = (text) => (hasTime(text) ? minuteOf(text) : (dayNumber(text) + 1) * MIN_PER_DAY);
const stamp = (minute) => {
  const day = Math.floor(minute / MIN_PER_DAY);
  const m = minute - day * MIN_PER_DAY;
  return `${dateText(day)} ${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};
// the hours a size names ("15m", "1h", "4h"), in minutes; an hour for a size named otherwise
const sizeMinutes = (size) => {
  const m = /^(\d+(?:\.\d+)?)(m|h)$/.exec(size || "");
  return m ? Number(m[1]) * (m[2] === "h" ? 60 : 1) : 60;
};
// [from, to) in minutes. Planned dates as written; actual and estimated times as they are.
const span = (task) => {
  if (task.dragged) return task.dragged;
  if (task.basis === "planned") {
    const from = planStart(task.start);
    return [from, Math.max(planEnd(task.end || task.start), from + 1)];
  }
  const from = minuteOf(task.start);
  // a task in progress has no end yet: it runs until now (the report guesses an end from its size, days away)
  const end = task.state === "doing" && task.basis === "actual" ? Math.min(minuteOf(task.end), Math.max(nowMinute(), from + 1)) : minuteOf(task.end);
  return [from, Math.max(end, from + 1)];
};
// A task with neither actual times nor planned dates has no place on the axis.
const dated = (task) => task.basis !== "unscheduled";
const datedTasks = (works) => works.flatMap((work) => work.tasks.filter(dated));
// The whole days a bar covers, which is what dragging moves.
const barDays = (task) => {
  const [from, to] = span(task);
  return [Math.floor(from / MIN_PER_DAY), Math.ceil(to / MIN_PER_DAY) - 1];
};

function readLine(line, fields) {
  const attrs = {};
  for (const [, name, value] of line.matchAll(ATTR)) attrs[name] = value;
  const start = attrs[fields.start_plan];
  const due = attrs[fields.due_plan];
  const planned = !attrs[fields.start] && DATE.test(start || "") && DATE.test(due || "") && planStart(start) < planEnd(due);
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
    else if (task.basis === "planned" && line.state === "todo") {
      // its planned dates were taken off the line: it waits for a date again
      task.basis = "unscheduled";
      delete task.start;
      delete task.end;
    }
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

// The file with the task's planned dates set (or, with no plan, taken off), or null when the task has started or its line is gone.
function withPlannedDates(text, id, plan, fields) {
  const lines = text.split("\n");
  const at = lines.findIndex((line) => (line.match(TASK_LINE) || [])[2] === id);
  if (at < 0 || readLine(lines[at], fields).state !== "todo") return null;
  lines[at] = plan
    ? setAttr(setAttr(lines[at], fields.start_plan, plan.start, fields.unknown), fields.due_plan, plan.due, fields.unknown)
    : lines[at]
        .replace(ATTR, (whole, key) => (key === fields.start_plan || key === fields.due_plan ? "" : whole))
        .replace(/ {2,}/g, " ")
        .trimEnd();
  return lines.join("\n").replace(/^(---\n(?:(?!---\n)[\s\S])*?\nupdated:[ \t]*)[^\n]*/, (_, before) => before + dateText(todayNumber()));
}

// [from, to) in minutes after a drag by `by` minutes, kept within [first, last) and at least one step long.
function dragged(mode, from, to, by, first, last, step) {
  if (mode === "start") return [Math.max(first, Math.min(from + by, to - step)), to];
  if (mode === "end") return [from, Math.min(last, Math.max(to + by, from + step))];
  const moved = Math.max(first - from, Math.min(by, last - to));
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

// Busy stretches [from, to) in minutes, joined when the time between them is shorter than `gap`.
function busyRanges(spans, gap) {
  const ranges = [];
  for (const [from, to] of [...spans].sort((a, b) => a[0] - b[0])) {
    const last = ranges[ranges.length - 1];
    if (last && from - last[1] < gap) last[1] = Math.max(last[1], to);
    else ranges.push([from, to]);
  }
  return ranges;
}

// Lay busy stretches side by side: columns of `slot` minutes, a folded strip between two stretches.
// Every piece is a whole number of columns wide, so the grid stays even across the folds.
function piecesOf(ranges, slot) {
  const pieces = [];
  let x = 0;
  for (const [from, to] of ranges) {
    const start = Math.floor(from / slot) * slot;
    const end = Math.max(Math.ceil(to / slot) * slot, start + slot);
    const last = pieces[pieces.length - 1];
    if (last && start <= last.to) {
      // joined once rounded to whole columns
      const to = Math.max(last.to, end);
      last.width += ((to - last.to) / slot) * DAY_WIDTH;
      last.to = to;
      x = last.x + last.width;
      continue;
    }
    if (last) {
      pieces.push({ from: last.to, to: start, x, width: FOLD_COLUMNS * DAY_WIDTH, fold: true });
      x += FOLD_COLUMNS * DAY_WIDTH;
    }
    const width = ((end - start) / slot) * DAY_WIDTH;
    pieces.push({ from: start, to: end, x, width, fold: false });
    x += width;
  }
  return pieces;
}

// The chart's time axis: its column size, and the pieces of time it shows left to right.
function scaleFor(data, today, room) {
  const spans = datedTasks(data.works).map(span);
  const busy = busyRanges(spans, FOLD_MINUTES);
  if (spans.length && busy.reduce((sum, [from, to]) => sum + to - from, 0) <= FINE_HOURS * 60) {
    // two columns on the left for a pinned date, and two after each stretch for the text beside its last bars
    const fits = (slot) => {
      const pieces = piecesOf(busy.map(([from, to], i) => [i === 0 ? from - 2 * slot : from, to + 2 * slot]), slot);
      return { slot, pieces, width: pieces.reduce((sum, p) => sum + p.width, 0) };
    };
    const choices = FINE_SLOTS.map(fits);
    // when it can't all fit, scrolling is needed anyway: then the finest that keeps each busy stretch within the note
    const widest = (scale) => Math.max(...scale.pieces.filter((p) => !p.fold).map((p) => p.width));
    return (
      choices.find((scale) => scale.width <= room) || choices.find((scale) => widest(scale) <= room) || choices[choices.length - 1]
    );
  }
  const days = [today];
  for (const work of data.works) {
    if (work.idea) days.push(dayNumber(work.idea.date));
    if (work.created) days.push(dayNumber(work.created));
    for (const task of work.tasks.filter(dated)) days.push(...barDays(task));
  }
  // a little before the first day, and room after today and the last day to drag into
  const last = Math.max(today + 30, Math.max(...days) + 14);
  const dayRanges = busyRanges(
    [...days.map((day) => [day, day + 1]), [today, last + 1]],
    FOLD_DAYS + 1,
  ).map(([from, to], i) => [(i === 0 ? from - 2 : from) * MIN_PER_DAY, to * MIN_PER_DAY]);
  const pieces = piecesOf(dayRanges, MIN_PER_DAY);
  return { slot: MIN_PER_DAY, pieces, width: pieces.reduce((sum, p) => sum + p.width, 0) };
}

// Where a minute falls on the chart; before the first piece or after the last it carries on at that piece's pace.
function xOf(scale, minute) {
  const { pieces } = scale;
  const piece = pieces.find((p) => minute < p.to) || pieces[pieces.length - 1];
  const at = minute < pieces[0].from ? pieces[0] : piece;
  return at.x + ((minute - at.from) / (at.to - at.from)) * at.width;
}

// The minute at a point on the chart.
function minuteAt(scale, x) {
  const { pieces } = scale;
  const piece = pieces.find((p) => x < p.x + p.width) || pieces[pieces.length - 1];
  const at = x < 0 ? pieces[0] : piece;
  return at.from + ((x - at.x) / at.width) * (at.to - at.from);
}

const isDays = (scale) => scale.slot === MIN_PER_DAY;

// [from, to) as drawn: whole days on a day chart, the actual minutes on a finer one.
function drawnSpan(task, scale) {
  const [from, to] = span(task);
  if (!isDays(scale)) return [from, to];
  const [first, last] = barDays(task);
  return [first * MIN_PER_DAY, (last + 1) * MIN_PER_DAY];
}

const padOf = (scale) => (isDays(scale) ? 2 : 1);
const widthOf = ([from, to], scale) => Math.max(MIN_BAR, xOf(scale, to) - xOf(scale, from) - 2 * padOf(scale));

function place(bar, drawn, scale) {
  bar.style.left = `${xOf(scale, drawn[0]) + padOf(scale)}px`;
  bar.style.width = `${widthOf(drawn, scale)}px`;
}

// Text beside a bar, for a name too long for it or a work's total.
function besideBar(track, className, text, drawn, scale) {
  const label = make(track, className, text);
  label.style.left = `${xOf(scale, drawn[0]) + padOf(scale) + widthOf(drawn, scale) + 4}px`;
  return label;
}

function besideMark(track, text, title) {
  const label = make(track, "lt-mark-date", text);
  label.title = title;
}

// "34분", "1시간 20분", "2일 3시간": the two largest units, in the report's language.
function duration(minutes, labels) {
  const unit = (key, n, fallback) => (labels[key] || fallback).replace("{n}", n);
  const days = Math.floor(minutes / MIN_PER_DAY);
  const hours = Math.floor((minutes % MIN_PER_DAY) / 60);
  const mins = Math.round(minutes % 60);
  const parts = days
    ? [unit("days", days, "{n} d"), hours && unit("hours", hours, "{n} h")]
    : hours
      ? [unit("hours", hours, "{n} h"), mins && unit("minutes", mins, "{n} min")]
      : [unit("minutes", mins, "{n} min")];
  return parts.filter(Boolean).join(" ");
}

function drawHeader(body, scale, today, labels) {
  const months = make(body, "lt-row lt-months");
  make(months, "lt-name");
  const monthTrack = make(months, "lt-track");
  const days = make(body, "lt-row lt-days");
  make(days, "lt-name");
  const dayTrack = make(days, "lt-track");
  // the upper row names the date (the month on a day chart) over the columns that belong to it
  const group = (minute) => (isDays(scale) ? dateText(Math.floor(minute / MIN_PER_DAY)).slice(0, 7) : dateText(Math.floor(minute / MIN_PER_DAY)));
  let named = ""; // a date already named before a fold isn't named again after it
  for (const piece of scale.pieces) {
    if (piece.fold) {
      make(monthTrack, "lt-month lt-month-fold").style.width = `${piece.width}px`;
      const cell = make(dayTrack, "lt-day lt-fold-label", `⋯ ${duration(piece.to - piece.from, labels)} ⋯`);
      cell.style.flexBasis = `${piece.width}px`;
      continue;
    }
    let groupStart = piece.from;
    for (let minute = piece.from; minute < piece.to; minute += scale.slot) {
      if (isDays(scale)) {
        const day = minute / MIN_PER_DAY;
        const date = dateOf(day);
        const cell = make(dayTrack, "lt-day", String(date.getUTCDate()));
        if ([0, 6].includes(date.getUTCDay())) cell.classList.add("lt-weekend");
        if (day === today) cell.classList.add("lt-today-cell");
      } else {
        // the hour at each hour's first column
        const hour = String(Math.floor(minute / 60) % 24).padStart(2, "0");
        make(dayTrack, "lt-day", minute % 60 === 0 ? (labels.hour || "{hour}").replace("{hour}", hour) : "");
      }
      const next = minute + scale.slot;
      if (next >= piece.to || group(next) !== group(minute)) {
        const name = group(minute) === named ? "" : group(minute);
        named = group(minute);
        make(monthTrack, "lt-month", name).style.width = `${((next - groupStart) / scale.slot) * DAY_WIDTH}px`;
        groupStart = next;
      }
    }
  }
}

// A small arrow drawn like the chart's own lines, for the legend.
function arrowSwatch(parent, className) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "lt-swatch-arrow");
  svg.setAttribute("viewBox", "0 0 22 10");
  for (const [d, cls] of [
    ["M1 5H16", `lt-arrow ${className}`],
    ["M21 5l-5 -3v6z", `lt-arrow lt-arrow-head ${className}`],
  ]) {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("class", cls);
    svg.appendChild(path);
  }
  parent.appendChild(svg);
}

// A line through the points, with its corners rounded.
function roundedPath(points, radius = 4) {
  let d = `M${points[0][0]} ${points[0][1]}`;
  for (let i = 1; i < points.length - 1; i++) {
    const [[px, py], [x, y], [nx, ny]] = [points[i - 1], points[i], points[i + 1]];
    const r = Math.min(radius, Math.hypot(x - px, y - py) / 2, Math.hypot(nx - x, ny - y) / 2);
    const toward = (ax, ay, len) => [x + Math.sign(ax - x) * len, y + Math.sign(ay - y) * len];
    const [ax, ay] = toward(px, py, r);
    const [bx, by] = toward(nx, ny, r);
    d += `L${ax} ${ay}Q${x} ${y} ${bx} ${by}`;
  }
  const [lx, ly] = points[points.length - 1];
  return `${d}L${lx} ${ly}`;
}

// Draw the lines between tasks. Between two finished tasks a line waits hidden until one of them is pointed at.
// Tells whether any line flags a task starting too early, and whether any waits hidden.
function drawArrows(svg, shown, scale) {
  svg.replaceChildren();
  const found = { late: false, quiet: false };
  const add = (d, className, ends) => {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("class", className);
    path.dataset.ends = ends;
    svg.appendChild(path);
  };
  const rows = new Map(shown.map((task, row) => [task.fullId, { task, y: HEADER_HEIGHT + row * ROW_HEIGHT + ROW_HEIGHT / 2 }]));
  for (const [, { task, y }] of rows) {
    for (const id of task.after || []) {
      const before = rows.get(id);
      if (!before || !dated(before.task) || !dated(task)) continue;
      const beforeSpan = drawnSpan(before.task, scale);
      const from = drawnSpan(task, scale)[0];
      // from the bar's right edge, which a very short task's least width may push past its end
      const x1 = xOf(scale, beforeSpan[0]) + padOf(scale) + widthOf(beforeSpan, scale);
      const x2 = xOf(scale, from) + 2;
      // what already happened can't be fixed, so only a task still to come is flagged
      // (on a day chart, starting on the day the task before ends is on time)
      // a planned date has no time of day, so a task planned for the day its prerequisite ends is in order
      const late = task.state === "todo" && barDays(task)[0] < barDays(before.task)[1];
      // what is finished is history: its lines stay out of the way until asked for
      const quiet = !late && task.state === "done" && before.task.state === "done";
      const room = x2 >= x1 + 12;
      // a task to come that starts right as the one before ends needs no line; looping one around it only tangles the chart
      if (!room && !late && !quiet) continue;
      const middle = y - Math.sign(y - before.y) * (ROW_HEIGHT / 2);
      const points = room
        ? [[x1, before.y], [(x1 + x2) / 2, before.y], [(x1 + x2) / 2, y], [x2 - 4, y]]
        : [[x1, before.y], [x1 + 5, before.y], [x1 + 5, middle], [x2 - 7, middle], [x2 - 7, y], [x2 - 4, y]];
      const cls = `lt-arrow${late ? " lt-arrow-late" : ""}${quiet ? " lt-arrow-quiet" : ""}`;
      found.late = found.late || late;
      found.quiet = found.quiet || quiet;
      const ends = `${id} ${task.fullId}`;
      add(roundedPath(points), cls, ends);
      add(`M${x2} ${y}l-5 -3v6z`, `${cls} lt-arrow-head`, ends);
    }
  }
  return found;
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
    // the columns are chosen to fit the note, so a note that turns out wider or narrower is drawn again
    const resized = new ResizeObserver(() => {
      if (Math.abs(this.el.clientWidth - this.drawnWidth) > 40) this.draw();
    });
    resized.observe(this.el);
    this.register(() => resized.disconnect());
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

  // A plan for a task, from [from, to) in minutes: whole days are written as dates, anything finer with its time.
  plan([from, to]) {
    const whole = from % MIN_PER_DAY === 0 && to % MIN_PER_DAY === 0;
    return whole ? { start: dateText(from / MIN_PER_DAY), due: dateText(to / MIN_PER_DAY - 1) } : { start: stamp(from), due: stamp(to) };
  }

  // Write a task's planned dates, or take them off (plan null) so it waits for a date again.
  async save(work, task, plan) {
    const before = { start: task.start, end: task.end, basis: task.basis };
    if (plan) Object.assign(task, { start: plan.start, end: plan.due, basis: "planned" });
    else Object.assign(task, { start: undefined, end: undefined, basis: "unscheduled" });
    this.draw();
    const file = this.app.vault.getAbstractFileByPath(work.file);
    let saved = false;
    if (file instanceof TFile) {
      await this.app.vault.process(file, (text) => {
        const changed = withPlannedDates(text, task.fullId, plan, this.data.fields);
        saved = changed !== null;
        return saved ? changed : text;
      });
    }
    if (saved) return;
    Object.assign(task, before);
    new Notice(this.data.labels.not_saved);
    this.draw();
  }

  // Is the pointer over the "no date yet" column, or over a day of the chart (and which minute)?
  dropAt(e) {
    const under = document.elementsFromPoint(e.clientX, e.clientY).filter((el) => this.el.contains(el));
    if (under.some((el) => el.classList.contains("lt-tray"))) return { tray: true };
    const track = under.find((el) => el.classList.contains("lt-track") && !el.closest(".lt-months, .lt-days"));
    return track ? { minute: minuteAt(this.scale, e.clientX - track.getBoundingClientRect().left) } : null;
  }

  // Move or stretch a planned task; dropped on the "no date yet" column, it loses its dates.
  // A plan without a time moves by days; one with a time moves by the chart's columns, keeping its time.
  startDrag(event, work, task, bar, mode) {
    event.preventDefault();
    event.stopPropagation();
    bar.setPointerCapture(event.pointerId);
    const scale = this.scale;
    const [from, to] = drawnSpan(task, scale);
    const step = isDays(scale) || !hasTime(task.start) ? MIN_PER_DAY : scale.slot;
    const { pieces } = scale;
    const first = Math.ceil(pieces[0].from / step) * step;
    const last = Math.floor(pieces[pieces.length - 1].to / step) * step;
    const track = bar.parentElement;
    const at = (clientX) => minuteAt(scale, clientX - track.getBoundingClientRect().left);
    const startMinute = at(event.clientX);
    const tip = make(track, "lt-tip");
    this.dragging = true;
    let toTray = false;
    const show = (by) => {
      task.dragged = dragged(mode, from, to, Math.round(by / step) * step, first, last, step);
      place(bar, task.dragged, scale);
      if (bar.caption) bar.caption.textContent = this.caption(task);
      const plan = this.plan(task.dragged);
      tip.textContent = toTray ? this.data.labels.unscheduled || "" : `${plan.start} → ${plan.due}`;
      tip.style.left = `${xOf(scale, task.dragged[1]) + 4}px`;
      this.arrows();
    };
    const onMove = (e) => {
      toTray = Boolean((this.dropAt(e) || {}).tray);
      show(at(e.clientX) - startMinute);
    };
    const stop = (e) => {
      bar.removeEventListener("pointermove", onMove);
      bar.removeEventListener("pointerup", stop);
      bar.removeEventListener("pointercancel", stop);
      tip.remove();
      this.dragging = false;
      const moved = task.dragged;
      delete task.dragged;
      const fail = (error) => new Notice(`Lantern Timeline: ${error.message}`);
      if (e.type === "pointerup" && toTray) this.save(work, task, null).catch(fail);
      else if (e.type === "pointerup" && moved && (moved[0] !== from || moved[1] !== to)) this.save(work, task, this.plan(moved)).catch(fail);
      else this.draw();
    };
    bar.addEventListener("pointermove", onMove);
    bar.addEventListener("pointerup", stop);
    bar.addEventListener("pointercancel", stop);
    show(0);
  }

  drawWork(body, work, scale) {
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
    const placed = work.tasks.filter(dated);
    this.trayCell(row, work.tasks.length - placed.length, work);
    if (placed.length) {
      const spans = placed.map((task) => drawnSpan(task, scale));
      const whole = [Math.min(...spans.map((s) => s[0])), Math.max(...spans.map((s) => s[1]))];
      const summary = make(track, "lt-bar lt-summary");
      place(summary, whole, scale);
      // a finished work shows how long its tasks took, added up, and how long it took from first start to last end
      if (labels.worked && work.tasks.every((task) => task.state === "done" && task.basis === "actual")) {
        const times = work.tasks.map(span);
        const worked = times.reduce((sum, [from, to]) => sum + to - from, 0);
        const taken = Math.max(...times.map((s) => s[1])) - Math.min(...times.map((s) => s[0]));
        const total = besideBar(track, "lt-total", duration(worked, labels), whole, scale);
        total.title = summary.title = `${labels.worked} ${duration(worked, labels)} · ${labels.elapsed} ${duration(taken, labels)}`;
      }
    }
    for (const [date, label, cls] of [
      [work.idea && work.idea.date, work.idea && `${work.idea.id} · ${labels.idea}`, "lt-mark-idea"],
      [work.created, labels.plan, "lt-mark-plan"],
    ]) {
      if (!date) continue;
      // a date has no time: the middle of its column on a day chart, the start of the day on a finer one
      const at = xOf(scale, dayNumber(date) * MIN_PER_DAY) + (isDays(scale) ? DAY_WIDTH / 2 : 0) - 5;
      if (at > scale.width) continue;
      const mark = make(track, `lt-mark ${cls}`);
      mark.style.left = `${Math.max(at, 8)}px`;
      mark.title = `${label} · ${date}`;
      // a day before a finer chart begins keeps its mark at the left edge, with the date it stands for
      if (at < 0) besideMark(track, `◂ ${date.slice(5, 10)}`, mark.title);
    }
    if (!isOpen) return [];

    for (const task of work.tasks) {
      const line = make(body, "lt-row lt-task");
      const link = make(make(line, "lt-name"), "lt-task-name", `${task.id} ${task.title}`);
      link.title = `${task.id} ${task.title}`;
      link.addEventListener("click", () => this.app.workspace.openLinkText(work.file, this.sourcePath));
      line.addEventListener("mouseenter", () => this.focus(task, true));
      line.addEventListener("mouseleave", () => this.focus(task, false));
      const track = make(line, "lt-track");
      const tray = this.trayCell(line);
      if (!dated(task)) {
        // no date yet: its size waits in the column on the right, to be dragged onto a day
        const chip = make(tray, "lt-chip", task.size ? `${task.id} · ${task.size}` : task.id);
        chip.title = `${task.id} ${task.title}`;
        if (this.data.fields) chip.addEventListener("pointerdown", (event) => this.startPlace(event, work, task, chip));
        continue;
      }
      // a plan with no time is a day to do it in, drawn as that day rather than as hours of work
      const dayPlan = task.basis === "planned" && !hasTime(task.start) ? " lt-day-plan" : "";
      const who = task.who ? ` lt-who-${task.who}` : "";
      const bar = make(track, `lt-bar lt-task-bar lt-${task.state} lt-${task.basis}${dayPlan}${who}`);
      const caption = make(bar, "lt-bar-text", this.caption(task));
      place(bar, drawnSpan(task, scale), scale);
      const end = task.basis === "estimated" ? dateText(barDays(task)[1]) : task.end;
      const lines = [`${task.id} ${task.title}`, `${task.start} → ${end}`, `${labels[task.state]} · ${labels[task.basis]}`];
      if (task.basis === "planned" && task.size) lines.push(`${labels.size_label || ""} ${task.size}`.trim());
      if (task.by && task.by.length) lines.push(`${labels.by || ""}: ${task.by.join(", ")}`);
      bar.title = lines.join("\n");
      bar.caption = caption;
      if (labels.needs) {
        // a task of the same work goes by its short id, one of another work by its full id
        const ids = (task.after || []).map((id) => (id.startsWith(`${work.id}-`) ? id.slice(work.id.length + 1) : id));
        bar.title += `\n${ids.length ? labels.needs.replace("{ids}", ids.join(", ")) : labels.needs_none}`;
      }
      // only a task that has not started can move: actual times stay as they happened
      if (task.state !== "todo" || !this.data.fields) continue;
      bar.classList.add("lt-movable");
      make(bar, "lt-handle lt-handle-start").dataset.mode = "start";
      make(bar, "lt-handle lt-handle-end").dataset.mode = "end";
      bar.addEventListener("pointerdown", (event) => this.startDrag(event, work, task, bar, event.target.dataset.mode || "move"));
    }
    return work.tasks;
  }

  // A bar's text, from where it starts: a finished task with how long it took, a plan with a time with how long it is
  // planned for (it follows a drag), a plan for a day with its size.
  caption(task) {
    const labels = this.data.labels;
    const [from, to] = span(task);
    if (task.state === "done" && task.basis === "actual") return `${task.id} · ${duration(to - from, labels)}`;
    if (task.basis === "planned" && (task.dragged || hasTime(task.start))) return `${task.id} · ${duration(to - from, labels)}`;
    if (task.basis === "planned" && task.size) return `${task.id} · ${task.size}`;
    return task.id;
  }

  // where the open works begin, for a finer chart to open at: today may be far from them
  openStart() {
    const open = this.data.works.filter((work) => this.folds.get(work.id) && work.tasks.some(dated));
    const tasks = datedTasks(open.length ? open : this.data.works);
    return tasks.length ? Math.min(...tasks.map((task) => span(task)[0])) : nowMinute();
  }

  // The cell of the "no date yet" column at the end of a row, when the chart has one; a work's row shows how many wait.
  trayCell(row, waiting = 0, work = null) {
    if (!this.trayWidth) return null;
    const cell = make(row, "lt-tray");
    if (waiting) {
      const count = make(cell, "lt-tray-count", String(waiting));
      // a work's count opens the work, so its undated tasks show as chips to drag
      if (work) count.addEventListener("click", () => {
        this.folds.set(work.id, true);
        this.draw();
      });
    }
    return cell;
  }

  // Drag a task with no date onto the chart. On a day chart it gets that day; on a finer chart it starts at the column
  // it is dropped on and lasts as long as its size says (1h is an hour).
  startPlace(event, work, task, chip) {
    event.preventDefault();
    chip.setPointerCapture(event.pointerId);
    const scale = this.scale;
    const ghost = make(document.body, "lt-chip lt-chip-ghost", chip.textContent);
    let plan = null;
    const planAt = (e) => {
      const drop = this.dropAt(e);
      if (!drop || drop.tray) return null;
      if (isDays(scale)) {
        const day = Math.floor(drop.minute / MIN_PER_DAY);
        return { start: dateText(day), due: dateText(day) };
      }
      const from = Math.floor(drop.minute / scale.slot) * scale.slot;
      return this.plan([from, from + sizeMinutes(task.size)]);
    };
    const onMove = (e) => {
      plan = planAt(e);
      ghost.style.left = `${e.clientX + 10}px`;
      ghost.style.top = `${e.clientY + 10}px`;
      ghost.textContent = plan ? `${chip.textContent} → ${plan.start === plan.due ? plan.start : `${plan.start} – ${plan.due.slice(-5)}`}` : chip.textContent;
    };
    const stop = (e) => {
      chip.removeEventListener("pointermove", onMove);
      chip.removeEventListener("pointerup", stop);
      chip.removeEventListener("pointercancel", stop);
      ghost.remove();
      if (e.type === "pointerup" && plan) this.save(work, task, plan).catch((error) => new Notice(`Lantern Timeline: ${error.message}`));
    };
    chip.addEventListener("pointermove", onMove);
    chip.addEventListener("pointerup", stop);
    chip.addEventListener("pointercancel", stop);
    onMove(event);
  }

  arrows() {
    return drawArrows(this.svg, this.shown, this.scale);
  }

  // Only what the chart has, after the size of one column.
  drawLegend(legend, scale, lines) {
    const { labels, works } = this.data;
    const tasks = works.flatMap((work) => work.tasks);
    const kind = (t) => (t.state !== "todo" ? t.state : t.basis === "estimated" || t.basis === "unscheduled" ? t.basis : "todo");
    const has = new Set(tasks.map(kind));
    for (const task of tasks) if (task.who) has.add(`who_${task.who}`);
    if (tasks.some(dated)) has.add("span");
    if (works.some((work) => work.idea)) has.add("idea");
    if (works.some((work) => work.created)) has.add("plan");
    if (tasks.some((task) => (task.after || []).length)) has.add("after");
    if (lines.late) has.add("late");
    if (labels.column) make(legend, "lt-legend-item lt-legend-column", labels.column.replace("{size}", duration(scale.slot, labels)));
    for (const [cls, key, name] of [
      ["lt-swatch lt-bar lt-task-bar lt-done lt-actual", "done", "done"],
      ["lt-swatch lt-bar lt-task-bar lt-doing lt-actual", "doing", "doing"],
      ["lt-swatch lt-bar lt-task-bar lt-who-human", "who_human", "who_human"],
      ["lt-swatch lt-bar lt-task-bar lt-who-both", "who_both", "who_both"],
      ["lt-swatch lt-bar lt-task-bar lt-who-ai", "who_ai", "who_ai"],
      ["lt-swatch lt-bar lt-task-bar lt-todo lt-planned", "todo", "legend_todo"],
      ["lt-swatch lt-bar lt-task-bar lt-todo lt-estimated", "estimated", "legend_estimated"], // in a report written by an older version
      ["lt-chip lt-chip-swatch", "unscheduled", "unscheduled"],
      ["lt-swatch lt-bar lt-summary", "span", "span"],
      ["lt-mark lt-mark-idea", "idea", "idea"],
      ["lt-mark lt-mark-plan", "plan", "plan"],
      ["lt-arrow-focus", "after", "after"],
      ["lt-arrow-late", "late", "late"],
    ]) {
      const text = labels[name] || labels[key]; // a report written by an older version has fewer labels
      if (!text || !has.has(key)) continue;
      const item = make(legend, "lt-legend-item");
      if (key === "after" || key === "late") arrowSwatch(item, cls);
      else make(item, cls);
      make(item, "", text);
    }
    if (lines.quiet && labels.after_hint) make(legend, "lt-legend-item lt-legend-hint", labels.after_hint);
  }

  // ◀ [date ▾] ▶ over a chart wider than the note: the days with tasks, one list however many there are.
  // Choosing a day puts its start at the chart's left edge. Returns what to call after scrolling.
  drawDateNav(root, scroller, scale) {
    const days = [...new Set(datedTasks(this.data.works).map((task) => Math.floor(span(task)[0] / MIN_PER_DAY)))];
    days.sort((a, b) => a - b);
    if (days.length < 2) return () => {};
    const nav = document.createElement("div");
    nav.className = "lt-nav";
    root.insertBefore(nav, scroller);
    const button = (text, onClick) => {
      const el = document.createElement("button");
      el.textContent = text;
      el.addEventListener("click", onClick);
      nav.appendChild(el);
    };
    const select = document.createElement("select");
    select.className = "dropdown";
    for (const day of days) {
      const option = document.createElement("option");
      option.value = String(day);
      option.textContent = dateText(day);
      select.appendChild(option);
    }
    // a day's start, or where its time comes back from a fold
    const startOf = (day) => {
      const minute = Math.max(day * MIN_PER_DAY, scale.pieces[0].from);
      const piece = scale.pieces.find((p) => minute < p.to);
      return piece && piece.fold ? piece.to : minute;
    };
    const go = (day) => scroller.scrollTo({ left: Math.max(0, xOf(scale, startOf(day))), behavior: "smooth" });
    const current = () => {
      const day = Math.floor(minuteAt(scale, scroller.scrollLeft + 1) / MIN_PER_DAY);
      return days.filter((d) => d <= day).pop() ?? days[0];
    };
    const step = (by) => go(days[Math.min(days.length - 1, Math.max(0, days.indexOf(current()) + by))]);
    button("◀", () => step(-1));
    nav.appendChild(select);
    button("▶", () => step(1));
    select.addEventListener("change", () => go(Number(select.value)));
    const show = () => {
      nav.hidden = scroller.scrollWidth <= scroller.clientWidth + 1; // all of it fits: nothing to move to
      select.value = String(current());
    };
    scroller.addEventListener("scroll", show);
    return show;
  }

  // Show the lines into one task — what had to finish before it — or hide them again.
  focus(task, on) {
    for (const path of this.svg.querySelectorAll("path")) {
      if (path.dataset.ends.split(" ")[1] === task.fullId) path.classList.toggle("lt-arrow-focus", on);
    }
  }

  draw() {
    if (this.dragging) return;
    const old = this.scroller;
    const scrollMinute = old && minuteAt(this.scale, old.scrollLeft);
    const scrollTop = old ? old.scrollTop : 0;
    const today = todayNumber();
    const data = this.data;
    this.drawnWidth = this.el.clientWidth;
    const undated = (work) => work.tasks.some((task) => !dated(task));
    const wide = this.trayWide || data.works.some((work) => this.folds.get(work.id) && undated(work));
    // a planned task not started can be dragged back to it, so the column stays (narrow) while there is one
    const movable = data.works.some((work) => work.tasks.some((task) => task.basis === "planned" && task.state === "todo"));
    this.trayWidth = data.works.some(undated) ? (wide ? TRAY_WIDTH : TRAY_NARROW) : movable && this.data.fields ? TRAY_NARROW : 0;

    const room = Math.max((this.el.clientWidth || 700) - NAME_WIDTH - this.trayWidth - 16, 280);
    const scale = (this.scale = scaleFor(data, today, room));
    const root = document.createElement("div");
    root.className = "lt-root";
    const legend = make(root, "lt-legend");

    const scroller = make(root, "lt-scroller");
    const body = make(scroller, "lt-body");
    const trackWidth = scale.width;
    body.style.width = `${NAME_WIDTH + trackWidth + this.trayWidth}px`;
    body.style.setProperty("--lt-tray-width", `${this.trayWidth}px`);
    body.style.setProperty("--lt-name-width", `${NAME_WIDTH}px`);
    body.style.setProperty("--lt-day-width", `${DAY_WIDTH}px`);
    body.style.setProperty("--lt-track-width", `${trackWidth}px`);
    if (isDays(scale) && scale.pieces.length === 1) {
      // the week tile starts with its shaded days, so it is shifted to start on a Saturday
      const saturday = (6 - dateOf(scale.pieces[0].from / MIN_PER_DAY).getUTCDay() + 7) % 7;
      body.style.setProperty("--lt-weekend-shift", `${saturday * DAY_WIDTH}px`);
    } else {
      body.classList.add("lt-fine"); // the grid only: a week tile can't follow columns or folds
      root.classList.add("lt-fine"); // and the legend shows planned days the way the chart does
    }

    drawHeader(body, scale, today, data.labels);
    const [months, daysRow] = body.children;
    this.trayCell(months);
    const head = this.trayCell(daysRow);
    if (head) {
      head.textContent = this.trayWidth === TRAY_WIDTH ? data.labels.unscheduled || "" : "◂";
      head.title = data.labels.unscheduled || "";
      head.classList.add("lt-tray-head");
      head.addEventListener("click", () => {
        this.trayWide = this.trayWidth !== TRAY_WIDTH;
        this.draw();
      });
    }
    this.shown = [];
    for (const work of data.works) {
      this.shown.push({}, ...this.drawWork(body, work, scale)); // the work's own row, then its open tasks
    }
    this.svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    this.svg.setAttribute("class", "lt-arrows");
    this.svg.setAttribute("width", trackWidth);
    this.svg.setAttribute("height", HEADER_HEIGHT + this.shown.length * ROW_HEIGHT);
    this.svg.style.left = `${NAME_WIDTH}px`;
    body.appendChild(this.svg);
    this.drawLegend(legend, scale, this.arrows());
    for (const piece of scale.pieces.filter((p) => p.fold)) {
      const strip = make(body, "lt-fold");
      strip.style.left = `${NAME_WIDTH + piece.x}px`;
      strip.style.width = `${piece.width}px`;
      strip.title = duration(piece.to - piece.from, data.labels);
    }
    const now = isDays(scale) ? today * MIN_PER_DAY + MIN_PER_DAY / 2 : nowMinute();
    const nowX = xOf(scale, now);
    if (nowX >= 0 && nowX <= trackWidth) make(body, "lt-today").style.left = `${NAME_WIDTH + nowX}px`;

    this.el.replaceChildren(root);
    this.scroller = scroller;
    const showDay = this.drawDateNav(root, scroller, scale);
    const scroll = () => {
      const visible = Math.max(scroller.clientWidth - NAME_WIDTH, 0);
      const start = isDays(scale) ? nowX - visible / 2 : xOf(scale, this.openStart()) - 2 * DAY_WIDTH;
      scroller.scrollLeft = old ? xOf(scale, scrollMinute) : Math.max(0, start);
      scroller.scrollTop = scrollTop;
      body.classList.toggle("lt-scrolls", scroller.scrollWidth > scroller.clientWidth + 1);
      showDay();
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
