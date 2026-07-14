const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("astracortexDesktop", {
  platform: process.platform,
  isDesktop: true,
});
