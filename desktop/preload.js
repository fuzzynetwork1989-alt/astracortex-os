const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("astracortexDesktop", {
  platform: process.platform,
  isDesktop: true,
  version: "2.1.0",
});
