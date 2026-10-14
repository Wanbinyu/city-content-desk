const DEMO = {
  url: "https://v.douyin.com/example-beijing/",
  title: "北京双眼皮机构对照表",
  city: "武汉",
  from_city: "",
  topic: "双眼皮",
  source: "user",
  table_text: "1、北京示例机构甲：把项目和复查分开问\n2、北京示例机构乙：费用组成当面核对\n3、北京示例机构丙：不要只对照别人的成片\nhttps://v.douyin.com/example-beijing/\n",
  notes: "把示例机构甲改成江汉示例",
  caption: "",
};

function $(id) {
  return document.getElementById(id);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}

function readForm() {
  const form = new FormData($("form"));
  return Object.fromEntries(form.entries());
}

function fillForm(values) {
  const form = $("form");
  Object.entries(values).forEach(([key, value]) => {
    if (form.elements[key]) form.elements[key].value = value;
  });
  const source = form.querySelector(`input[name=source][value="${values.source || "user"}"]`);
  if (source) source.checked = true;
}

function csvCell(value) {
  const text = String(value ?? "");
  if (/[",\n\r]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

function writeTableText(columns, rows) {
  const lines = [columns, ...rows].map((row) => row.map(csvCell).join(","));
  $("form").elements.table_text.value = lines.join("\n");
}

function renderEditor(result) {
  const columns = result.columns.map((column) => column);
  const rows = result.rows.map((row) => row.slice());
  writeTableText(columns, rows);
  const wrap = document.createElement("div");
  wrap.className = "editor-wrap";
  const table = document.createElement("table");
  table.className = "editor";

  function sync() {
    writeTableText(columns, rows);
    draw();
  }

  function draw() {
    table.replaceChildren();
    const head = document.createElement("tr");
    columns.forEach((column, index) => {
      const cell = document.createElement("th");
      const input = document.createElement("input");
      input.value = column;
      input.setAttribute("aria-label", "表头");
      input.addEventListener("input", () => {
        columns[index] = input.value;
        writeTableText(columns, rows);
      });
      cell.appendChild(input);
      head.appendChild(cell);
    });
    head.appendChild(document.createElement("th"));
    table.appendChild(head);
    rows.forEach((row, rowIndex) => {
      const line = document.createElement("tr");
      row.forEach((value, columnIndex) => {
        const cell = document.createElement("td");
        const input = document.createElement("input");
        input.value = value;
        input.setAttribute("aria-label", `${columns[columnIndex] || "单元格"} 第${rowIndex + 1}行`);
        input.addEventListener("input", () => {
          rows[rowIndex][columnIndex] = input.value;
          writeTableText(columns, rows);
        });
        cell.appendChild(input);
        line.appendChild(cell);
      });
      const removeCell = document.createElement("td");
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "row-remove";
      remove.textContent = "删除";
      remove.addEventListener("click", () => {
        if (rows.length === 1) return;
        rows.splice(rowIndex, 1);
        sync();
      });
      removeCell.appendChild(remove);
      line.appendChild(removeCell);
      table.appendChild(line);
    });
  }

  draw();
  wrap.appendChild(table);
  const add = document.createElement("button");
  add.type = "button";
  add.textContent = "加一行";
  add.addEventListener("click", () => {
    rows.push(columns.map(() => ""));
    sync();
  });
  const box = document.createElement("div");
  box.appendChild(wrap);
  box.appendChild(add);
  return box;
}

function renderResult(result) {
  const root = $("result");
  root.replaceChildren();
  root.appendChild(Object.assign(document.createElement("h2"), { textContent: result.title }));
  if (result.note) {
    root.appendChild(Object.assign(document.createElement("p"), { className: "hint", textContent: result.note }));
  }
  if (result.risks && result.risks.length) {
    const risk = document.createElement("p");
    risk.className = "risk";
    risk.textContent = "这些词发布前要改掉：" + result.risks.join("、");
    root.appendChild(risk);
  }
  $("form").elements.title.value = result.title;
  $("form").elements.caption.value = result.caption;

  const watch = document.createElement("div");
  watch.className = "watch";
  if (!result.preview && result.page_url) {
    const stage = document.createElement("div");
    stage.className = "stage";
    const frame = document.createElement("iframe");
    frame.src = result.page_url;
    frame.title = "表格页面";
    stage.appendChild(frame);
    watch.appendChild(stage);
  }
  const side = document.createElement("div");
  side.className = "side";
  if (result.video_url) {
    const media = document.createElement("div");
    media.appendChild(Object.assign(document.createElement("p"), { className: "kicker", textContent: "视频" }));
    const video = document.createElement("video");
    video.controls = true;
    video.src = result.video_url;
    media.appendChild(video);
    side.appendChild(media);
  } else if (result.video_message) {
    side.appendChild(Object.assign(document.createElement("p"), { className: "hint", textContent: result.video_message }));
  }
  const words = document.createElement("div");
  words.appendChild(Object.assign(document.createElement("p"), { className: "kicker", textContent: "文案" }));
  words.appendChild(Object.assign(document.createElement("pre"), { className: "copy", textContent: result.caption }));
  side.appendChild(words);
  watch.appendChild(side);
  root.appendChild(watch);

  const details = document.createElement("details");
  if (result.preview) details.open = true;
  details.appendChild(Object.assign(document.createElement("summary"), { textContent: "改表格后再生成" }));
  details.appendChild(renderEditor(result));
  root.appendChild(details);
}

document.querySelectorAll(".tab").forEach((node) => {
  node.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("on"));
    node.classList.add("on");
    ["work", "settings"].forEach((name) => {
      $(`tab-${name}`).hidden = name !== node.dataset.tab;
    });
  });
});

$("demo").addEventListener("click", () => fillForm(DEMO));

async function submitTable(preview) {
  const message = $("form-msg");
  message.textContent = preview ? "正在整理表格" : "正在生成页面和视频";
  try {
    const body = readForm();
    if (preview) body.preview = true;
    const result = await api("/api/table", {
      method: "POST",
      body: JSON.stringify(body),
    });
    message.textContent = preview ? "表格已整理，可以改完再生成" : (result.video_url ? "页面和视频已生成" : "页面已生成");
    renderResult(result);
  } catch (error) {
    message.textContent = error.message;
  }
}

$("preview").addEventListener("click", () => submitTable(true));

$("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitTable(false);
});

$("settings").addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = Object.fromEntries(new FormData(event.target).entries());
  try {
    const saved = await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
    ["llm_base_url", "llm_model", "llm_api_key", "f2_cookie"].forEach((name) => {
      event.target.elements[name].value = saved[name] || "";
    });
    $("settings-msg").textContent = "已保存";
  } catch (error) {
    $("settings-msg").textContent = error.message;
  }
});

api("/api/settings").then((settings) => {
  const form = $("settings");
  ["llm_base_url", "llm_model", "llm_api_key", "f2_cookie"].forEach((name) => {
    form.elements[name].value = settings[name] || "";
  });
}).catch(() => {});
