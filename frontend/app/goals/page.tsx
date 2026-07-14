"use client";

import Shell from "@/components/Shell";
import { api, getApiUrl, loadAuth, readSSE } from "@/lib/api";
import { useState } from "react";

/** Full cognitive OS loop UI (plan → act → reflect). */
export default function GoalsPage() {
  const [goal, setGoal] = useState("");
  const [autonomy, setAutonomy] = useState("full");
  const [answer, setAnswer] = useState("");
  const [events, setEvents] = useState<string[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  function push(line: string) {
    setEvents((e) => [...e.slice(-100), line]);
  }

  async function run() {
    const auth = loadAuth();
    if (!auth || !goal.trim()) return;
    setRunning(true);
    setAnswer("");
    setEvents([]);
    try {
      const start = await api<{ task_id: string }>(
        "/chat",
        { method: "POST", body: JSON.stringify({ goal, autonomy, use_rag: true }) },
        auth.access_token
      );
      setTaskId(start.task_id);
      push(`task ${start.task_id}`);
      await readSSE(`${getApiUrl()}/chat/stream/${start.task_id}`, auth.access_token, (event, data) => {
        if (event === "token") setAnswer((a) => a + String(data.token || ""));
        else if (event === "plan") push(`plan v${data.version} · ${((data.steps as unknown[]) || []).length} steps`);
        else if (event === "tool_call") push(`tool ${data.tool_name} ${data.success ? "ok" : "fail"}`);
        else if (event === "reflection") push(`reflection q=${data.quality_score}`);
        else if (event === "done") {
          if (data.answer) setAnswer(String(data.answer));
          push(`done ${data.status}`);
        } else if (event === "error") push(`error ${data.detail}`);
        else push(event);
      });
    } catch (e) {
      push(String((e as Error).message));
    } finally {
      setRunning(false);
    }
  }

  return (
    <Shell title="Goals / OS Loop">
      <h1>Cognitive OS loop</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Full planner → tools → critic → memory write path from the master list.
      </p>
      <div className="panel stack">
        <textarea rows={4} value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="Describe a real goal…" />
        <div className="row">
          <select value={autonomy} onChange={(e) => setAutonomy(e.target.value)} style={{ maxWidth: 240 }}>
            <option value="suggest">suggest</option>
            <option value="act_with_approval">act_with_approval</option>
            <option value="full">full</option>
          </select>
          <button onClick={run} disabled={running || !goal.trim()}>
            {running ? "Running…" : "Run OS loop"}
          </button>
        </div>
        {taskId && <div className="muted">Task {taskId}</div>}
      </div>
      <div className="panel">
        <h2>Answer</h2>
        <div className="msg-body">{answer || "—"}</div>
      </div>
      <div className="panel">
        <h2>Events</h2>
        <pre className="event-log">{events.join("\n")}</pre>
      </div>
    </Shell>
  );
}
