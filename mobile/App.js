import React, { useEffect, useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  ScrollView,
  StatusBar,
  Platform,
  KeyboardAvoidingView,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { StatusBar as ExpoStatusBar } from "expo-status-bar";
import Constants from "expo-constants";

/**
 * Resolve API base:
 * - EXPO_PUBLIC_API_URL env
 * - saved override
 * - Android emulator: 10.0.2.2
 * - Device / default: LAN IP baked at build or localhost
 */
const DEFAULT_API =
  process.env.EXPO_PUBLIC_API_URL ||
  (Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://127.0.0.1:8000");

async function getApiBase() {
  const saved = await AsyncStorage.getItem("astracortex_api_url");
  return (saved || DEFAULT_API).replace(/\/$/, "");
}

async function api(path, options = {}, token) {
  const base = await getApiBase();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${base}${path}`, { ...options, headers });
  if (!res.ok) {
    const t = await res.text();
    let detail = t;
    try {
      const j = JSON.parse(t);
      if (j.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch (_) {}
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

export default function App() {
  const [screen, setScreen] = useState("login");
  const [auth, setAuth] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("Ready");
  const [sessionId, setSessionId] = useState(null);
  const [apiUrl, setApiUrl] = useState(DEFAULT_API);
  const [health, setHealth] = useState("");

  useEffect(() => {
    (async () => {
      const base = await getApiBase();
      setApiUrl(base);
      const raw = await AsyncStorage.getItem("astracortex_auth");
      if (raw) {
        setAuth(JSON.parse(raw));
        setScreen("chat");
      }
      try {
        const h = await fetch(`${base}/health`);
        setHealth(h.ok ? "API online" : `API HTTP ${h.status}`);
      } catch (e) {
        setHealth(`API offline · ${base}`);
      }
    })();
  }, []);

  async function saveApiUrl() {
    await AsyncStorage.setItem("astracortex_api_url", apiUrl.replace(/\/$/, ""));
    setStatus("API URL saved");
    try {
      const h = await fetch(`${apiUrl.replace(/\/$/, "")}/health`);
      setHealth(h.ok ? "API online" : `API HTTP ${h.status}`);
    } catch {
      setHealth("API offline");
    }
  }

  async function loginOrRegister(mode) {
    setBusy(true);
    setError("");
    try {
      const path = mode === "login" ? "/auth/login" : "/auth/register";
      const body =
        mode === "login"
          ? { email, password }
          : { email, password, name: "Mobile Operator", org_name: "Astra Mobile" };
      const data = await api(path, { method: "POST", body: JSON.stringify(body) });
      await AsyncStorage.setItem("astracortex_auth", JSON.stringify(data));
      setAuth(data);
      setScreen("chat");
      setStatus("Signed in");
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function sendChat() {
    if (!auth || !message.trim()) return;
    setBusy(true);
    setError("");
    const userText = message.trim();
    setMessage("");
    setMessages((m) => [...m, { role: "user", content: userText }, { role: "assistant", content: "…" }]);
    setStatus("Generating… (first reply can take 20–60s)");
    try {
      const reply = await api(
        "/converse/reply",
        {
          method: "POST",
          body: JSON.stringify({
            session_id: sessionId,
            message: userText,
            tier: "seed",
            use_rag: false,
          }),
        },
        auth.access_token
      );
      setSessionId(reply.session_id);
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: reply.answer || "(empty)" };
        return copy;
      });
      setStatus(`Done · ${reply.model || "seed"} · ${reply.latency_ms ?? "?"}ms`);
    } catch (e) {
      const msg = String(e.message || e);
      setError(msg);
      setStatus("Error");
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: `Error: ${msg}` };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    await AsyncStorage.removeItem("astracortex_auth");
    setAuth(null);
    setMessages([]);
    setSessionId(null);
    setScreen("login");
  }

  if (screen === "login") {
    return (
      <SafeAreaView style={styles.root}>
        <ExpoStatusBar style="light" />
        <StatusBar barStyle="light-content" />
        <ScrollView contentContainerStyle={styles.card}>
          <Text style={styles.title}>AstraCortex</Text>
          <Text style={styles.sub}>Mobile cognitive OS · v2.1</Text>
          <Text style={styles.health}>{health}</Text>

          <Text style={styles.label}>API URL (phone: use PC Wi‑Fi IP)</Text>
          <TextInput
            style={styles.input}
            value={apiUrl}
            onChangeText={setApiUrl}
            autoCapitalize="none"
            placeholder="http://192.168.x.x:8000"
            placeholderTextColor="#8b97ab"
          />
          <TouchableOpacity style={[styles.btn, styles.btnSecondary]} onPress={saveApiUrl}>
            <Text style={styles.btnText}>Save API URL</Text>
          </TouchableOpacity>

          <TextInput
            style={styles.input}
            placeholder="Email"
            placeholderTextColor="#8b97ab"
            autoCapitalize="none"
            keyboardType="email-address"
            value={email}
            onChangeText={setEmail}
          />
          <TextInput
            style={styles.input}
            placeholder="Password (min 8)"
            placeholderTextColor="#8b97ab"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />
          {!!error && <Text style={styles.error}>{error}</Text>}
          {busy ? (
            <ActivityIndicator color="#5b8cff" />
          ) : (
            <View style={styles.row}>
              <TouchableOpacity style={styles.btn} onPress={() => loginOrRegister("register")}>
                <Text style={styles.btnText}>Register</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.btn, styles.btnSecondary]}
                onPress={() => loginOrRegister("login")}
              >
                <Text style={styles.btnText}>Login</Text>
              </TouchableOpacity>
            </View>
          )}
          <Text style={styles.hint}>
            Emulator uses 10.0.2.2:8000. Physical device: set API to your PC IP (e.g. http://192.168.10.55:8000)
            and allow Windows Firewall for port 8000.
          </Text>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root}>
      <ExpoStatusBar style="light" />
      <View style={styles.top}>
        <View>
          <Text style={styles.titleSmall}>AstraCortex</Text>
          <Text style={styles.subTiny}>{status}</Text>
        </View>
        <View style={styles.row}>
          <TouchableOpacity onPress={() => setScreen("chat")}>
            <Text style={styles.link}>Chat</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={logout}>
            <Text style={styles.link}>Out</Text>
          </TouchableOpacity>
        </View>
      </View>

      <FlatList
        style={{ flex: 1, padding: 12 }}
        data={messages}
        keyExtractor={(_, i) => String(i)}
        renderItem={({ item }) => (
          <View style={[styles.bubble, item.role === "user" ? styles.user : styles.assistant]}>
            <Text style={styles.bubbleText}>{item.content}</Text>
          </View>
        )}
        ListEmptyComponent={
          <Text style={styles.sub}>Ask anything. Seed tier replies in seconds after model load.</Text>
        }
      />
      {!!error && <Text style={styles.error}>{error}</Text>}
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <View style={styles.composer}>
          <TextInput
            style={[styles.input, { flex: 1, marginBottom: 0 }]}
            placeholder="Message…"
            placeholderTextColor="#8b97ab"
            value={message}
            onChangeText={setMessage}
          />
          <TouchableOpacity style={styles.btn} onPress={sendChat} disabled={busy}>
            {busy ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.btnText}>Send</Text>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0a0c10" },
  card: { margin: 16, padding: 20, backgroundColor: "#151a23", borderRadius: 16, gap: 12 },
  title: { color: "#fff", fontSize: 28, fontWeight: "800" },
  titleSmall: { color: "#fff", fontSize: 18, fontWeight: "700" },
  sub: { color: "#8b97ab", marginBottom: 4 },
  subTiny: { color: "#8b97ab", fontSize: 11 },
  health: { color: "#2ee6a6", fontSize: 12, marginBottom: 8 },
  label: { color: "#8b97ab", fontSize: 12 },
  input: {
    backgroundColor: "#11151c",
    borderColor: "#2a3344",
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    color: "#eef2f8",
    marginBottom: 8,
  },
  row: { flexDirection: "row", gap: 10, alignItems: "center" },
  btn: {
    backgroundColor: "#5b8cff",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 12,
    minWidth: 72,
    alignItems: "center",
  },
  btnSecondary: { backgroundColor: "#2a3344" },
  btnText: { color: "#fff", fontWeight: "700" },
  error: { color: "#ff5c7a", padding: 8 },
  top: {
    padding: 14,
    borderBottomColor: "#2a3344",
    borderBottomWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  link: { color: "#9db7ff", marginLeft: 12, fontWeight: "600" },
  bubble: { padding: 12, borderRadius: 14, marginBottom: 10, maxWidth: "92%" },
  user: { backgroundColor: "#1e3a6e", alignSelf: "flex-end" },
  assistant: { backgroundColor: "#171d28", alignSelf: "flex-start" },
  bubbleText: { color: "#eef2f8", lineHeight: 20 },
  composer: {
    flexDirection: "row",
    gap: 8,
    padding: 12,
    borderTopColor: "#2a3344",
    borderTopWidth: 1,
    alignItems: "center",
  },
  hint: { color: "#8b97ab", fontSize: 11, marginTop: 8, lineHeight: 16 },
});
