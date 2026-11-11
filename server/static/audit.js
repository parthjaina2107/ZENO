async function loadAudit() {
  const status = document.getElementById("status");
  const rows = document.getElementById("events");
  rows.replaceChildren();
  const token = sessionStorage.getItem("voice_agent_jwt");
  if (!token) {
    status.textContent = "Sign in at the ZENO control page first.";
    return;
  }
  try {
    const response = await fetch("/api/audit", {headers: {Authorization: "Bearer " + token}});
    if (!response.ok) {
      status.textContent = response.status === 401 ? "Sign in again to view the audit trail." : "Could not load the audit trail.";
      return;
    }
    const data = await response.json();
    for (const event of data.events.reverse()) {
      const row = rows.insertRow();
      const outcome = event.success != null ? (event.success ? "success" : "failed")
        : event.approved != null ? (event.approved ? "approved" : "denied") : "—";
      for (const value of [new Date(event.timestamp).toLocaleString(), event.event, event.action_type, outcome]) {
        row.insertCell().textContent = value ?? "—";
      }
    }
    status.textContent = "Showing " + data.events.length + " newest events.";
    if (data.skipped) status.textContent += " Skipped " + data.skipped + " unreadable records.";
    if (data.truncated) status.textContent += " Older records are outside the scan limit.";
  } catch {
    status.textContent = "Could not load the audit trail.";
  }
}
document.getElementById("refresh").addEventListener("click", loadAudit);
loadAudit();
