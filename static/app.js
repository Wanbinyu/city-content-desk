const STATUS = {
  inbox: "待选",
  broken: "已拆解",
  drafted: "已出稿",
  approved: "已通过",
  queued: "待发布",
};

const state = {
  posts: [],
  currentId: null,
  filter: "all",
  settings: {},
  notice: "",
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
  if (!response.ok) {
    throw new Error(data.error || "请求失败");
  }
  return data;
}

function text(tag, value, className) {
  const node = document.createElement(tag);
  node.textContent = value == null ? "" : String(value);
  if (className) node.className = className;
  return node;
}

function button(label, className, onClick) {
  const node = document.createElement("button");
  node.type = "button";
  node.textContent = label;
  if (className) node.className = className;
  node.addEventListener("click", onClick);
  return node;
}

function field(label, value, attrs) {
  const wrap = document.createElement("label");
  wrap.textContent = label;
  const input = document.createElement(attrs.multiline ? "textarea" : "input");
  if (attrs.multiline) input.rows = attrs.rows || 6;
  input.value = value || "";
  input.dataset.field = attrs.field;
  wrap.appendChild(input);
  return wrap;
}

function notify(text) {
  state.notice = text || "";
}

function current() {
  return state.posts.find((post) => post.id === state.currentId) || null;
}

function visiblePosts() {
  return state.posts.filter((post) => {
    if (state.filter === "all") return true;
    if (state.filter === "risk") return Boolean(post.breakdown_risks);
    return (post.keyword || "").includes(state.filter) || (post.title || "").includes(state.filter);
  });
}

async function reload(keepId) {
  const data = await api("/api/board");
  state.posts = data.posts;
  if (keepId && state.posts.some((post) => post.id === keepId)) {
    state.currentId = keepId;
  } else if (!current()) {
    state.currentId = state.posts.length ? state.posts[0].id : null;
  }
  renderList();
  renderDetail();
}

function renderList() {
  const posts = visiblePosts();
  $("list-count").textContent = `${posts.length} 条`;
  const list = $("list");
  list.replaceChildren();
  posts.forEach((post) => {
    const node = document.createElement("button");
    node.type = "button";
    node.className = post.id === state.currentId ? "post on" : "post";
    node.appendChild(text("b", post.title));
    const bits = [
      post.keyword || "未标城市",
      `${post.liked_count} 赞`,
      STATUS[post.status] || post.status,
      post.source,
    ];
    if (post.breakdown_risks) bits.push("有风险词");
    node.appendChild(text("span", bits.join(" · ")));
    node.addEventListener("click", () => {
      if (post.id !== state.currentId) state.notice = "";
      state.currentId = post.id;
      renderList();
      renderDetail();
    });
    list.appendChild(node);
  });
}

function renderDetail() {
  const root = $("detail");
  const post = current();
  root.replaceChildren();
  if (!post) {
    root.appendChild(text("p", "还没有热帖。到「导入」贴表格、JSON 或链接。", "empty"));
    return;
  }
  root.appendChild(text("h2", post.title));
  if (state.notice) root.appendChild(text("p", state.notice, "ok"));
  const meta = document.createElement("p");
  meta.className = "meta";
  meta.append(
    text("span", post.author || "未知作者"),
    text("span", `${post.liked_count} 赞`),
    text("span", `${post.comment_count} 评论`),
    text("span", STATUS[post.status] || post.status),
  );
  root.appendChild(meta);
  if (post.aweme_url) {
    const link = document.createElement("a");
    link.href = post.aweme_url;
    link.textContent = post.aweme_url;
    link.target = "_blank";
    link.rel = "noreferrer";
    root.appendChild(link);
  }
  root.appendChild(text("h3", "口播"));
  const transcript = document.createElement("textarea");
  transcript.rows = 5;
  transcript.value = post.transcript || "";
  root.appendChild(transcript);
  const transcriptRow = document.createElement("div");
  transcriptRow.className = "row";
  transcriptRow.append(
    button("保存口播", "", async () => {
      try {
        await api(`/api/posts/${post.id}/transcript`, {
          method: "POST",
          body: JSON.stringify({ transcript: transcript.value }),
        });
        notify("口播已保存");
        await reload(post.id);
      } catch (error) {
        notify(error.message);
        renderDetail();
      }
    }),
    button("用 f2 读取文案", "", async () => {
      notify("正在调用 f2，可能需要一两分钟");
      renderDetail();
      try {
        await api(`/api/posts/${post.id}/fetch`, { method: "POST", body: "{}" });
        notify("已从 f2 读到文案");
        await reload(post.id);
      } catch (error) {
        notify(error.message);
        renderDetail();
      }
    }),
  );
  root.appendChild(transcriptRow);

  root.appendChild(text("h3", "拆解"));
  if (post.structure) {
    const box = text("div", post.structure, "block");
    root.appendChild(box);
    const risk = post.breakdown_risks
      ? `风险词：${post.breakdown_risks}`
      : "这条口播里没有命中风险词";
    root.appendChild(text("p", risk, post.breakdown_risks ? "risk" : "ok"));
  }
  root.appendChild(button("拆解", "primary", async () => {
    try {
      if (transcript.value !== (post.transcript || "")) {
        await api(`/api/posts/${post.id}/transcript`, {
          method: "POST",
          body: JSON.stringify({ transcript: transcript.value }),
        });
      }
      await api(`/api/posts/${post.id}/breakdown`, { method: "POST", body: "{}" });
      notify("已拆解");
      await reload(post.id);
    } catch (error) {
      notify(error.message);
      renderDetail();
    }
  }));

  root.appendChild(text("h3", "复刻稿"));
  root.appendChild(text("p", "新稿不照搬原片原句。通过前会再拦一遍风险词。", "muted"));
  const draftFields = document.createElement("div");
  const inputs = {
    title: field("标题", post.draft_title, { field: "title" }),
    script: field("口播", post.draft_script, { field: "script", multiline: true, rows: 8 }),
    shots: field("分镜", post.draft_shots, { field: "shots", multiline: true, rows: 4 }),
    cover_text: field("封面文案", post.draft_cover, { field: "cover_text" }),
    tags: field("标签", post.draft_tags, { field: "tags" }),
  };
  Object.values(inputs).forEach((node) => draftFields.appendChild(node));
  root.appendChild(draftFields);
  if (post.draft_note) root.appendChild(text("p", post.draft_note, "warn"));
  if (post.draft_risks) root.appendChild(text("p", `稿内风险词：${post.draft_risks}`, "risk"));
  if (post.draft_engine) {
    root.appendChild(text("p", post.draft_engine === "llm" ? "这版来自大模型" : "这版是规则改写", "muted"));
  }

  const draftRow = document.createElement("div");
  draftRow.className = "row";
  draftRow.append(
    button("生成复刻稿", "primary", async () => {
      try {
        await api(`/api/posts/${post.id}/draft`, {
          method: "POST",
          body: JSON.stringify({ city: state.settings.city || "" }),
        });
        notify("已生成复刻稿");
        await reload(post.id);
      } catch (error) {
        notify(error.message);
        renderDetail();
      }
    }),
  );
  if (post.draft_id) {
    const readDraft = () => ({
      title: draftFields.querySelector("[data-field=title]").value,
      script: draftFields.querySelector("[data-field=script]").value,
      shots: draftFields.querySelector("[data-field=shots]").value,
      cover_text: draftFields.querySelector("[data-field=cover_text]").value,
      tags: draftFields.querySelector("[data-field=tags]").value,
    });
    draftRow.append(
      button("保存修改", "", async () => {
        try {
          await api(`/api/drafts/${post.draft_id}/body`, {
            method: "PUT",
            body: JSON.stringify(readDraft()),
          });
          notify("修改已保存");
          await reload(post.id);
        } catch (error) {
          notify(error.message);
          renderDetail();
        }
      }),
      button("通过", "", async () => {
        try {
          await api(`/api/drafts/${post.draft_id}/body`, {
            method: "PUT",
            body: JSON.stringify(readDraft()),
          });
          await api(`/api/drafts/${post.draft_id}/approve`, { method: "POST", body: "{}" });
          notify("已通过");
          await reload(post.id);
        } catch (error) {
          notify(error.message);
          renderDetail();
        }
      }),
      button("退回", "danger", async () => {
        try {
          await api(`/api/drafts/${post.draft_id}/reject`, { method: "POST", body: "{}" });
          notify("已退回，可以重写");
          await reload(post.id);
        } catch (error) {
          notify(error.message);
          renderDetail();
        }
      }),
    );
  }
  root.appendChild(draftRow);

  root.appendChild(text("h3", "发布包"));
  const account = document.createElement("input");
  account.placeholder = "发布账号名";
  account.value = state.settings.sau_account || "";
  const video = document.createElement("input");
  video.placeholder = "成片绝对路径，只在确认上传时需要";
  root.appendChild(account);
  root.appendChild(video);
  const publishRow = document.createElement("div");
  publishRow.className = "row";
  publishRow.append(
    button("生成发布包", "primary", async () => {
      if (!post.draft_id) {
        notify("先生成并通过复刻稿");
        renderDetail();
        return;
      }
      try {
        const result = await api(`/api/drafts/${post.draft_id}/package`, {
          method: "POST",
          body: JSON.stringify({ account: account.value, video_path: video.value, execute: false }),
        });
        notify(`${result.message} ${result.package_dir}`);
        await reload(post.id);
      } catch (error) {
        notify(error.message);
        renderDetail();
      }
    }),
    button("确认并上传", "danger", async () => {
      if (!window.confirm("确认这是本机构自己的成片，现在执行上传命令？")) return;
      try {
        const result = await api(`/api/drafts/${post.draft_id}/package`, {
          method: "POST",
          body: JSON.stringify({ account: account.value, video_path: video.value, execute: true }),
        });
        notify(result.message);
        await reload(post.id);
      } catch (error) {
        notify(error.message);
        renderDetail();
      }
    }),
  );
  root.appendChild(publishRow);
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((node) => {
    node.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("on"));
      node.classList.add("on");
      ["work", "import", "settings"].forEach((name) => {
        $(`tab-${name}`).hidden = name !== node.dataset.tab;
      });
    });
  });
  document.querySelectorAll(".chip").forEach((node) => {
    node.addEventListener("click", () => {
      document.querySelectorAll(".chip").forEach((item) => item.classList.remove("on"));
      node.classList.add("on");
      state.filter = node.dataset.filter;
      renderList();
    });
  });
}

function bindImport() {
  $("import-file").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    $("import-text").value = await file.text();
  });
  $("import-go").addEventListener("click", async () => {
    try {
      const result = await api("/api/import", {
        method: "POST",
        body: JSON.stringify({ text: $("import-text").value }),
      });
      $("import-msg").textContent = `识别 ${result.imported} 条，新增 ${result.added} 条`;
      await reload(state.currentId);
    } catch (error) {
      $("import-msg").textContent = error.message;
    }
  });
  $("load-demo").addEventListener("click", async () => {
    const result = await api("/api/sample", { method: "POST", body: "{}" });
    $("import-msg").textContent = `演示数据新增 ${result.added} 条`;
    await reload(state.currentId);
  });
}

function bindSettings() {
  $("settings").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const body = Object.fromEntries(form.entries());
    try {
      state.settings = await api("/api/settings", { method: "PUT", body: JSON.stringify(body) });
      fillSettings();
      $("settings-msg").textContent = "已保存到本机 data/settings.json";
    } catch (error) {
      $("settings-msg").textContent = error.message;
    }
  });
}

function fillSettings() {
  const form = $("settings");
  ["city", "selling_points", "llm_base_url", "llm_model", "llm_api_key", "sau_account", "f2_cookie"].forEach((name) => {
    form.elements[name].value = state.settings[name] || "";
  });
}

async function boot() {
  bindTabs();
  bindImport();
  bindSettings();
  state.settings = await api("/api/settings");
  fillSettings();
  await reload(null);
}

boot().catch((error) => {
  document.body.appendChild(text("p", error.message, "risk"));
});
