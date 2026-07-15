const { app, BrowserWindow, shell, Menu, dialog } = require("electron");
const path = require("path");

// Prefer local web UI; override with ASTRACORTEX_WEB_URL for cloud
const WEB_URL = process.env.ASTRACORTEX_WEB_URL || "http://127.0.0.1:3000";
const API_URL = process.env.ASTRACORTEX_API_URL || "http://127.0.0.1:8000";

let mainWindow = null;

function createMenu() {
  const template = [
    {
      label: "AstraCortex",
      submenu: [
        {
          label: "Reload",
          accelerator: "CmdOrCtrl+R",
          click: () => mainWindow?.webContents.reload(),
        },
        {
          label: "Open Web UI",
          click: () => shell.openExternal(WEB_URL),
        },
        {
          label: "API Health",
          click: async () => {
            try {
              const res = await fetch(`${API_URL}/health`);
              const j = await res.json();
              dialog.showMessageBox({
                type: "info",
                title: "API Health",
                message: j.status === "ok" ? "API online" : "API issue",
                detail: JSON.stringify(j.hybrid || j, null, 2).slice(0, 1500),
              });
            } catch (e) {
              dialog.showErrorBox(
                "API offline",
                `Cannot reach ${API_URL}\n\nStart: docker compose up -d postgres redis api\n\n${e.message}`
              );
            }
          },
        },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "toggleDevTools" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { role: "togglefullscreen" },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    title: "AstraCortex OS",
    backgroundColor: "#0a0c10",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow.show());

  mainWindow.loadURL(WEB_URL).catch(() => {
    mainWindow.loadURL(
      `data:text/html;charset=utf-8,${encodeURIComponent(`
      <html><body style="font-family:Segoe UI;background:#0a0c10;color:#eef2f8;padding:40px">
      <h1>AstraCortex OS</h1>
      <p>Web UI is not running at <code>${WEB_URL}</code>.</p>
      <p>Start it:</p>
      <pre style="background:#151a23;padding:16px;border-radius:12px">
cd astracortex/frontend
npm run start
      </pre>
      <p>Then reload this window (Ctrl+R).</p>
      </body></html>`)}`
    );
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.webContents.on("did-fail-load", (_e, code, desc) => {
    if (code === -106 || code === -105 || code === -102) {
      // ERR_INTERNET_DISCONNECTED / NAME_NOT_RESOLVED / CONNECTION_REFUSED
      mainWindow.loadURL(
        `data:text/html;charset=utf-8,${encodeURIComponent(`
        <html><body style="font-family:Segoe UI;background:#0a0c10;color:#eef2f8;padding:40px">
        <h1>Cannot reach UI</h1>
        <p>${desc} (${code})</p>
        <p>Start frontend + API, then press Ctrl+R.</p>
        </body></html>`)}`
      );
    }
  });
}

app.whenReady().then(() => {
  createMenu();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
