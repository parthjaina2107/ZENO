/* ZENO workspace. Conversation remains in memory; only preferences and the session credential persist. */
"use strict";
const $ = (id) => document.getElementById(id);
const storage = {
  get(k) {
    try {
      return localStorage.getItem(k);
    } catch {
      return null;
    }
  },
  set(k, v) {
    try {
      localStorage.setItem(k, v);
    } catch {}
  },
  remove(k) {
    try {
      localStorage.removeItem(k);
    } catch {}
  },
};
let socket,
  reconnectTimer,
  ready = false,
  busy = false,
  activeTask = null,
  permission = null,
  currentRun = null,
  recognition = null,
  recording = false,
  toastTimer;
const runs = [];
const terminal = new Set([
  "completed",
  "blocked",
  "cancelled",
  "failed",
  "needs_input",
]);
function icons() {
  window.lucide?.createIcons();
}
function notify(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").hidden = true), 5000);
}
function view(name) {
  document
    .querySelectorAll(".view")
    .forEach((el) => (el.hidden = el.id !== name));
  document.querySelectorAll(".nav").forEach((el) => {
    el.classList.toggle("active", el.dataset.view === name);
    if (el.dataset.view === name) el.setAttribute("aria-current", "page");
    else el.removeAttribute("aria-current");
  });
  $("pageTitle").textContent = name[0].toUpperCase() + name.slice(1);
  if (name === "activity") renderActivity();
}
document
  .querySelectorAll("[data-view]")
  .forEach((button) =>
    button.addEventListener("click", () => view(button.dataset.view)),
  );
function controls() {
  $("run").disabled = !ready || busy;
  $("mic").disabled = !ready || busy || !recognition;
  $("stop").disabled = !ready || !busy;
  document
    .querySelectorAll("[data-media]")
    .forEach((b) => (b.disabled = !ready || busy));
  $("mode").disabled = busy;
  $("run").firstChild.textContent = busy
    ? "Working…"
    : $("mode").value === "agent"
      ? "Run task"
      : "Run command";
  $("composerStatus").textContent = !ready
    ? "Waiting for connection"
    : busy
      ? "ZENO is working"
      : "Ready when you are";
}
function setConnection(connected, label) {
  ready = connected;
  $("statusText").textContent = label;
  $("connection").classList.toggle("online", connected);
  $("deviceStatus").textContent = connected
    ? "Connected · live telemetry"
    : "Host unavailable";
  if (!connected) {
    for (const key of ["cpu", "ram"]) {
      $(key).value = 0;
      $(key + "Value").textContent = "—";
    }
    $("batteryValue").textContent = "—";
  }
  controls();
}
function send(data) {
  if (socket?.readyState !== WebSocket.OPEN || (!ready && data.type !== "auth"))
    return false;
  socket.send(JSON.stringify(data));
  return true;
}
function speak(text) {
  if ($("speech").checked && "speechSynthesis" in window && !recording) {
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = $("language").value;
    speechSynthesis.speak(utterance);
  }
}
function message(text, sender = "agent", image) {
  $("chatEmpty")?.remove();
  const div = document.createElement("div");
  div.className = "message " + sender;
  const label = document.createElement("span");
  label.className = "sender";
  label.textContent = sender === "user" ? "YOU" : "ZENO";
  div.append(label, document.createTextNode(text || ""));
  if (image && /^data:image\/(png|jpeg|webp);base64,/.test(image)) {
    const img = document.createElement("img");
    img.src = image;
    img.alt = "Screenshot captured from the connected computer";
    div.append(img);
  }
  $("messages").append(div);
  $("messages").scrollTop = $("messages").scrollHeight;
  if (currentRun && sender === "agent") {
    currentRun.messages.push(text);
    renderActivity();
  }
}
function finish(status) {
  busy = false;
  activeTask = null;
  if (currentRun) currentRun.status = status;
  controls();
  renderActivity();
}
function dismissApproval() {
  permission = null;
  if ($("approval").open) $("approval").close();
}
function handle(data) {
  switch (data.type) {
    case "auth_ok":
      setConnection(true, "Connected");
      if ($("auth").open) $("auth").close();
      send({ type: "get_telemetry" });
      break;
    case "telemetry":
      for (const key of ["cpu", "ram"]) {
        const value = Number(data[key]);
        if (data[key] != null && Number.isFinite(value)) {
          $(key).value = value;
          $(key + "Value").textContent = Math.round(value) + "%";
        }
      }
      $("batteryValue").textContent =
        data.battery == null ? "Not available" : Math.round(data.battery) + "%";
      break;
    case "task_progress":
      if (activeTask !== data.task_id) {
        $("steps").replaceChildren();
        activeTask = data.task_id;
      }
      busy = !terminal.has(data.status);
      $("taskState").textContent = data.status
        .replaceAll("_", " ")
        .toUpperCase();
      $("taskTitle").textContent = terminal.has(data.status)
        ? data.status === "completed"
          ? "A little more done."
          : "Task " + data.status.replaceAll("_", " ")
        : currentRun?.text || "Working on your request";
      $("taskMessage").textContent = data.message;
      if (data.steps) {
        $("steps").replaceChildren();
        for (const text of data.steps) {
          const li = document.createElement("li");
          li.textContent =
            typeof text === "string" ? text : JSON.stringify(text);
          $("steps").append(li);
        }
      }
      Array.from($("steps").children).forEach((li, index) =>
        li.classList.toggle("done", index < (data.completed || 0)),
      );
      if (currentRun) currentRun.status = data.status;
      if (terminal.has(data.status)) {
        dismissApproval();
        message(data.message);
        speak(data.message);
        finish(data.status);
      }
      controls();
      renderActivity();
      break;
    case "response":
      message(data.message);
      speak(data.message);
      if (["abort", "cancelled"].includes(data.kind)) {
        dismissApproval();
        finish("cancelled");
      } else if (!activeTask) {
        dismissApproval();
        $("taskState").textContent = "RESPONSE RECEIVED";
        $("taskTitle").textContent = "Your request, answered.";
        $("taskMessage").textContent = data.message;
        finish("responded");
      }
      break;
    case "screenshot":
      message(data.message || "Your desktop screenshot.", "agent", data.data);
      if (!activeTask) finish("responded");
      break;
    case "permission_request":
      permission = data;
      busy = true;
      $("risk").textContent =
        (data.risk_level || "Review") + " · APPROVAL REQUIRED";
      $("approvalTitle").textContent = data.message?.startsWith(
        "Final confirmation:",
      )
        ? "One final confirmation."
        : "You decide what happens next.";
      $("approvalMessage").textContent = data.message || data.description;
      $("approvalDetails").textContent = JSON.stringify(
        { action: data.action_type, parameters: data.parameters },
        null,
        2,
      );
      if (!$("approval").open) $("approval").showModal();
      $("deny").focus();
      controls();
      break;
    case "error":
      message(data.message || "Something went wrong. Please try again.");
      dismissApproval();
      finish("failed");
      break;
  }
}
function connect() {
  clearTimeout(reconnectTimer);
  const token = storage.get("voice_agent_jwt");
  if (!token) {
    showAuth();
    return;
  }
  setConnection(false, "Connecting");
  const ws = new WebSocket(
    `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws`,
  );
  socket = ws;
  ws.onopen = () => {
    if (ws === socket) send({ type: "auth", token });
  };
  ws.onmessage = (event) => {
    if (ws !== socket) return;
    try {
      handle(JSON.parse(event.data));
    } catch {
      notify("An unreadable response arrived from the host.");
    }
  };
  ws.onclose = (event) => {
    if (ws !== socket) return;
    dismissApproval();
    recognition?.abort();
    if (busy) {
      message(
        "Connection lost. Further steps stop; an action already in progress may finish.",
      );
      finish("disconnected");
      $("taskState").textContent = "CONNECTION LOST";
      $("taskMessage").textContent = "Reconnect before starting another task.";
    }
    setConnection(false, "Disconnected");
    if ([4001, 4003].includes(event.code)) {
      storage.remove("voice_agent_jwt");
      showAuth("Your session expired. Please connect again.");
    } else if (storage.get("voice_agent_jwt")) {
      setConnection(false, "Reconnecting");
      reconnectTimer = setTimeout(connect, 3000);
    }
  };
  ws.onerror = () => {};
}
function showAuth(error = "") {
  setConnection(false, "Not connected");
  $("authError").textContent = error;
  if (!$("auth").open) $("auth").showModal();
  $("token").focus();
}
$("auth").addEventListener("cancel", (event) => event.preventDefault());
$("authForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = $("token").value.trim();
  if (!token) return;
  $("connect").disabled = true;
  $("connect").firstChild.textContent = "Connecting…";
  $("authError").textContent = "";
  try {
    const response = await fetch("/auth", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ token }),
      signal: AbortSignal.timeout(15000),
    });
    const data = await response.json();
    if (!response.ok || !data.jwt_token)
      throw new Error(data.detail || "Connection failed. Check your token.");
    storage.set("voice_agent_jwt", data.jwt_token);
    $("token").value = "";
    connect();
  } catch (error) {
    $("authError").textContent =
      error.name === "TimeoutError"
        ? "The host took too long to respond. Please retry."
        : error.message;
  } finally {
    $("connect").disabled = false;
    $("connect").firstChild.textContent = "Connect workspace";
  }
});
$("showToken").addEventListener("click", () => {
  const visible = $("token").type === "password";
  $("token").type = visible ? "text" : "password";
  $("showToken").setAttribute(
    "aria-label",
    visible ? "Hide access token" : "Show access token",
  );
});
$("disconnect").addEventListener("click", () => {
  if (busy) {
    notify("Stop the active task before disconnecting.");
    return;
  }
  clearTimeout(reconnectTimer);
  storage.remove("voice_agent_jwt");
  const old = socket;
  socket = null;
  old?.close();
  recognition?.abort();
  window.speechSynthesis?.cancel();
  showAuth();
});
function run(text = $("command").value.trim(), mode = $("mode").value) {
  if (!text) return;
  if (!ready || busy) {
    notify(
      busy
        ? "Wait for this task, or stop it first."
        : "Connect to your computer first.",
    );
    return;
  }
  recognition?.abort();
  window.speechSynthesis?.cancel();
  currentRun = {
    text,
    mode,
    status: "running",
    time: new Date(),
    messages: [],
  };
  runs.unshift(currentRun);
  busy = true;
  $("steps").replaceChildren();
  $("taskState").textContent = "STARTING";
  $("taskTitle").textContent = text;
  $("taskMessage").textContent = "Sending your request to ZENO.";
  message(text, "user");
  if (!send({ type: "command", text, mode })) {
    finish("failed");
    notify("Could not send the request.");
    return;
  }
  $("command").value = "";
  $("inputHint").textContent = "Enter to run · Shift + Enter for a new line";
  controls();
  renderActivity();
}
$("run").addEventListener("click", () => run());
$("mode").addEventListener("change", controls);
$("command").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    run();
  }
});
document.querySelectorAll("[data-prompt]").forEach((button) =>
  button.addEventListener("click", () => {
    view("workspace");
    $("command").value = button.dataset.prompt;
    $("command").focus();
  }),
);
document.querySelectorAll("[data-media]").forEach((button) =>
  button.addEventListener("click", () => {
    const commands = {
      previous: "previous song",
      next: "next track",
      play_pause: "play pause",
    };
    run(commands[button.dataset.media], "command");
  }),
);
function stop() {
  recognition?.abort();
  window.speechSynthesis?.cancel();
  if (send({ type: "abort" })) {
    $("taskState").textContent = "STOP REQUESTED";
    $("taskMessage").textContent =
      "Stopping further steps. An action in progress may finish.";
  }
  dismissApproval();
}
$("stop").addEventListener("click", stop);
$("approvalStop").addEventListener("click", stop);
function approve(approved) {
  if (!permission) return;
  send({
    type: "permission_response",
    request_id: permission.request_id,
    action_id: permission.action_id || null,
    approved,
  });
  message(approved ? "Action approved." : "Action denied.", "user");
  dismissApproval();
}
$("approve").addEventListener("click", () => approve(true));
$("deny").addEventListener("click", () => approve(false));
$("approval").addEventListener("cancel", (event) => {
  event.preventDefault();
  approve(false);
});
function renderActivity() {
  $("activityCount").textContent = runs.length;
  const list = $("activityList");
  list.replaceChildren();
  const query = $("activitySearch").value.toLowerCase();
  const filtered = runs.filter((run) => run.text.toLowerCase().includes(query));
  if (!filtered.length) {
    const empty = document.createElement("p");
    empty.textContent = runs.length
      ? "No matching requests. Try another search."
      : "Nothing here yet. Your first request starts the story.";
    list.append(empty);
    return;
  }
  for (const run of filtered) {
    const item = document.createElement("details");
    item.className = "activity-item";
    const summary = document.createElement("summary");
    summary.textContent = run.text;
    const meta = document.createElement("span");
    meta.textContent =
      run.time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) +
      " · " +
      run.status.replaceAll("_", " ");
    summary.append(meta);
    const p = document.createElement("p");
    p.textContent = run.messages.join("\n\n") || "Waiting for a response.";
    item.append(summary, p);
    list.append(item);
  }
}
$("activitySearch").addEventListener("input", renderActivity);
$("speech").checked = storage.get("zeno_speech") === "true";
$("motion").checked =
  storage.get("zeno_motion") === "true" ||
  matchMedia("(prefers-reduced-motion: reduce)").matches;
$("language").value = storage.get("zeno_language") || "en-US";
function preferences() {
  storage.set("zeno_speech", $("speech").checked);
  storage.set("zeno_motion", $("motion").checked);
  storage.set("zeno_language", $("language").value);
  document.body.classList.toggle("reduce-motion", $("motion").checked);
  if (!$("speech").checked) window.speechSynthesis?.cancel();
  if (recognition) {
    recognition.abort();
    recognition.lang = $("language").value;
  }
}
for (const id of ["speech", "motion", "language"])
  $(id).addEventListener("change", () => {
    preferences();
    notify("Preference saved.");
  });
document.body.classList.toggle("reduce-motion", $("motion").checked);
const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = $("language").value;
  recognition.onstart = () => {
    recording = true;
    $("mic").classList.add("recording");
    $("micLabel").textContent = "Finish listening";
    $("mic").setAttribute("aria-label", "Stop voice input");
    $("inputHint").textContent =
      "Listening… Your words appear here for review before running.";
  };
  recognition.onresult = (event) => {
    $("command").value = Array.from(event.results)
      .map((result) => result[0].transcript)
      .join(" ");
  };
  recognition.onerror = (event) => {
    const messages = {
      "not-allowed":
        "Microphone permission was denied. Allow it in browser settings, or type your request.",
      "audio-capture": "No microphone was found. You can type your request.",
      network:
        "Speech recognition could not connect. Please type your request.",
      "no-speech": "No speech detected. Try again or type your request.",
    };
    if (event.error !== "aborted")
      notify(
        messages[event.error] ||
          "Voice input is unavailable. Please type your request.",
      );
  };
  recognition.onend = () => {
    recording = false;
    $("mic").classList.remove("recording");
    $("micLabel").textContent = "Use your voice";
    $("mic").setAttribute("aria-label", "Start voice input");
    $("inputHint").textContent = $("command").value
      ? "Review your words, then choose Run."
      : "Enter to run · Shift + Enter for a new line";
  };
} else {
  $("micLabel").textContent = "Voice unavailable";
  $("inputHint").textContent =
    "Voice recognition is not supported here. Type your request instead.";
}
$("mic").addEventListener("click", () => {
  if (!recognition) return;
  if (recording) {
    recognition.stop();
    return;
  }
  window.speechSynthesis?.cancel();
  try {
    recognition.start();
  } catch {
    notify("Voice input is already starting.");
  }
});
function focusCommand() {
  view("workspace");
  $("command").focus();
  $("command").scrollIntoView({
    block: "center",
    behavior: $("motion").checked ? "instant" : "smooth",
  });
}
$("focusCommand").addEventListener("click", focusCommand);
document.addEventListener("keydown", (event) => {
  if (
    (event.ctrlKey || event.metaKey) &&
    event.key.toLowerCase() === "k" &&
    !$("auth").open &&
    !$("approval").open
  ) {
    event.preventDefault();
    focusCommand();
  }
});
$("today").textContent = new Date().toLocaleDateString(undefined, {
  weekday: "long",
  month: "long",
  day: "numeric",
});
setInterval(() => {
  if (ready) send({ type: "get_telemetry" });
}, 10000);
window.addEventListener("pagehide", () => {
  clearTimeout(reconnectTimer);
  socket?.close();
  recognition?.abort();
});
icons();
controls();
renderActivity();
connect();

$("settingsDisconnect").addEventListener("click", () =>
  $("disconnect").click(),
);

// One frame per pointer update; retain the native cursor and stationary controls.
const pointerSurface = document.createElement("div");
pointerSurface.className = "ambient-pointer";
pointerSurface.setAttribute("aria-hidden", "true");
document.body.prepend(pointerSurface);
const finePointer = matchMedia("(hover: hover) and (pointer: fine)");
const systemReducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
let pointerFrame = 0;
let pointerPosition = null;
let illuminatedPanel = null;
function clearPointerLight() {
  cancelAnimationFrame(pointerFrame);
  pointerFrame = 0;
  pointerPosition = null;
  document.body.classList.remove("pointer-active");
  illuminatedPanel?.classList.remove("pointer-lit");
  illuminatedPanel = null;
}
function paintPointerLight() {
  pointerFrame = 0;
  if (!pointerPosition) return;
  const { x, y, panel } = pointerPosition;
  pointerSurface.style.transform = `translate3d(${x}px, ${y}px, 0)`;
  document.body.classList.add("pointer-active");
  if (illuminatedPanel !== panel) {
    illuminatedPanel?.classList.remove("pointer-lit");
    illuminatedPanel = panel;
  }
  if (panel) {
    const bounds = panel.getBoundingClientRect();
    panel.style.setProperty("--pointer-x", `${x - bounds.left}px`);
    panel.style.setProperty("--pointer-y", `${y - bounds.top}px`);
    panel.classList.add("pointer-lit");
  }
}
document.addEventListener(
  "pointermove",
  (event) => {
    if (
      !finePointer.matches ||
      systemReducedMotion.matches ||
      $("motion").checked ||
      event.pointerType !== "mouse"
    ) {
      clearPointerLight();
      return;
    }
    pointerPosition = {
      x: event.clientX,
      y: event.clientY,
      panel:
        event.target instanceof Element ? event.target.closest(".glass") : null,
    };
    if (!pointerFrame) pointerFrame = requestAnimationFrame(paintPointerLight);
  },
  { passive: true },
);
document.documentElement.addEventListener("pointerleave", clearPointerLight);
window.addEventListener("blur", clearPointerLight);
window.addEventListener("scroll", clearPointerLight, { passive: true });
$("motion").addEventListener("change", clearPointerLight);
finePointer.addEventListener("change", clearPointerLight);
systemReducedMotion.addEventListener("change", clearPointerLight);
