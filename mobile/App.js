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
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { StatusBar as ExpoStatusBar } from "expo-status-bar";

// Android emulator → host machine. Device: set EXPO_PUBLIC_API_URL to your LAN IP.
const API_URL =
  process.env.EXPO_PUBLIC_API_URL ||
  (typeof window !== "undefined" ? "http://localhost:8000" : "http://10.0.2.2:8000");

async function api(path, options = {}, token) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) throw new Error(await res.text());
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
  const [metrics, setMetrics] = useState(null);
  const [sessionId, setSessionId] = useState(null);

  useEffect(() => {
    AsyncStorage.getItem("astracortex_auth").then((raw) => {
      if (raw) {
        const a = JSON.parse(raw);
        setAuth(a);
        setScreen("chat");
      }
    });
  }, []);

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
    try {
      const start = await api(
        "/converse",
        {
          method: "POST",
          body: JSON.stringify({
            session_id: sessionId,
            message: userText,
            tier: "nexus",
            use_rag: true,
          }),
        },
        auth.access_token
      );
      setSessionId(start.session_id);
      // Non-stream completion via OpenAI-compatible path if api_key present, else poll messages
      let answer = "";
      if (auth.api_key) {
        const completion = await fetch(`${API_URL}/v1/chat/completions`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${auth.api_key}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            model: "astracortex-nexus",
            messages: [
              ...messages.map((x) => ({ role: x.role, content: x.content })).filter((x) => x.content !== "…"),
              { role: "user", content: userText },
            ],
          }),
        });
        if (completion.ok) {
          const json = await completion.json();
          answer = json.choices?.[0]?.message?.content || "";
        }
      }
      if (!answer) {
        // Fallback: simple cognitive chat via register-session then wait on stream text buffer using fetch
        const streamRes = await fetch(
          `${API_URL}/converse/stream/${start.session_id}?tier=nexus&use_rag=true`,
          { headers: { Authorization: `Bearer ${auth.access_token}` } }
        );
        const text = await streamRes.text();
        const dones = [...text.matchAll(/event: done\ndata: (.*)/g)];
        if (dones.length) {
          try {
            answer = JSON.parse(dones[dones.length - 1][1]).answer || text.slice(-800);
          } catch {
            answer = text.slice(-800);
          }
        } else {
          const tokens = [...text.matchAll(/"token":\s*"((?:\\.|[^"\\])*)"/g)].map((m) => {
            try {
              return JSON.parse(`"${m[1]}"`);
            } catch {
              return m[1];
            }
          });
          answer = tokens.join("") || "No response";
        }
      }
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: answer };
        return copy;
      });
    } catch (e) {
      setError(String(e.message || e));
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: "Error: " + String(e.message || e) };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  async function loadMetrics() {
    if (!auth) return;
    try {
      setMetrics(await api("/metrics", {}, auth.access_token));
      setScreen("home");
    } catch (e) {
      setError(String(e.message || e));
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
        <View style={styles.card}>
          <Text style={styles.title}>AstraCortex</Text>
          <Text style={styles.sub}>Mobile cognitive OS</Text>
          <TextInput
            style={styles.input}
            placeholder="Email"
            placeholderTextColor="#8b97ab"
            autoCapitalize="none"
            value={email}
            onChangeText={setEmail}
          />
          <TextInput
            style={styles.input}
            placeholder="Password"
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
              <TouchableOpacity style={[styles.btn, styles.btnSecondary]} onPress={() => loginOrRegister("login")}>
                <Text style={styles.btnText}>Login</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root}>
      <ExpoStatusBar style="light" />
      <View style={styles.top}>
        <Text style={styles.titleSmall}>AstraCortex</Text>
        <View style={styles.row}>
          <TouchableOpacity onPress={() => setScreen("chat")}>
            <Text style={styles.link}>Chat</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={loadMetrics}>
            <Text style={styles.link}>Home</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={logout}>
            <Text style={styles.link}>Out</Text>
          </TouchableOpacity>
        </View>
      </View>

      {screen === "home" ? (
        <ScrollView style={{ padding: 16 }}>
          <Text style={styles.sub}>Dashboard</Text>
          <Text style={styles.mono}>{JSON.stringify(metrics, null, 2)}</Text>
        </ScrollView>
      ) : (
        <>
          <FlatList
            style={{ flex: 1, padding: 12 }}
            data={messages}
            keyExtractor={(_, i) => String(i)}
            renderItem={({ item }) => (
              <View style={[styles.bubble, item.role === "user" ? styles.user : styles.assistant]}>
                <Text style={styles.bubbleText}>{item.content}</Text>
              </View>
            )}
          />
          {!!error && <Text style={styles.error}>{error}</Text>}
          <View style={styles.composer}>
            <TextInput
              style={[styles.input, { flex: 1 }]}
              placeholder="Message…"
              placeholderTextColor="#8b97ab"
              value={message}
              onChangeText={setMessage}
            />
            <TouchableOpacity style={styles.btn} onPress={sendChat} disabled={busy}>
              <Text style={styles.btnText}>{busy ? "…" : "Send"}</Text>
            </TouchableOpacity>
          </View>
        </>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0a0c10" },
  card: { margin: 20, padding: 20, backgroundColor: "#151a23", borderRadius: 16, gap: 12 },
  title: { color: "#fff", fontSize: 28, fontWeight: "800" },
  titleSmall: { color: "#fff", fontSize: 18, fontWeight: "700" },
  sub: { color: "#8b97ab", marginBottom: 8 },
  input: {
    backgroundColor: "#11151c",
    borderColor: "#2a3344",
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    color: "#eef2f8",
  },
  row: { flexDirection: "row", gap: 10, alignItems: "center" },
  btn: {
    backgroundColor: "#5b8cff",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 12,
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
  mono: { color: "#8b97ab", fontFamily: "monospace", fontSize: 11 },
});
