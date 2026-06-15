/* @ds-bundle: {"format":3,"namespace":"BraveBearPlatformDesignSystemCopy_7e11fb","components":[{"name":"App","sourcePath":"uploads/mio-design-system.jsx"}],"sourceHashes":{"ui_kits/web/App.jsx":"a019fc4a4728","ui_kits/web/Composer.jsx":"c70bf15e0cbf","ui_kits/web/ContextPanel.jsx":"0d382d216c7c","ui_kits/web/Messages.jsx":"0a89a8ade28c","ui_kits/web/Primitives.jsx":"f7b54bfee989","ui_kits/web/Sidebar.jsx":"8b063eeb98b6","uploads/mio-design-system.jsx":"752bab60301a"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.BraveBearPlatformDesignSystemCopy_7e11fb = window.BraveBearPlatformDesignSystemCopy_7e11fb || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// ui_kits/web/App.jsx
try { (() => {
/* global React, Wordmark, Sidebar, ChatHeader, MessageList, Composer, ContextPanel */
const {
  useState: useStateApp,
  useEffect: useEffectApp
} = React;
const INITIAL_CHATS = [{
  id: "1",
  label: "Token scale calibration"
}, {
  id: "2",
  label: "Logo mark variants"
}, {
  id: "3",
  label: "Marketing site IA restructure"
}, {
  id: "4",
  label: "Client pitch — logo concepts"
}, {
  id: "5",
  label: "Server rack layout"
}];
const SEED_MESSAGES = {
  "1": [{
    id: 1,
    role: "user",
    text: "Can you help me check the accent reads correctly against the dark surface?"
  }, {
    id: 2,
    role: "ai",
    text: "Here's a clean approach. The near-white accent against the #1a1916 surface lands near 13:1 contrast — comfortably above AA for text and UI.",
    hasCode: true
  }, {
    id: 3,
    role: "user",
    text: "How do we keep the status colors from feeling hot on the lighter surface?"
  }, {
    id: 4,
    role: "ai",
    text: "Solid question. The status hues are tuned per theme — slightly lifted in dark, slightly deeper in light — so they stay legible without punching against the surface."
  }]
};
const AI_REPLIES = ["Let me think through that. The cleanest path is usually to anchor on the warm neutrals first, then bring the accent in where it earns attention.", "Noted. I'd lean toward the hairline treatment here — keeps the surfaces feeling considered rather than decorated.", "Good framing. Two reasonable takes; I'll sketch both against the mark so you can see which holds up at favicon scale."];
function App() {
  const [theme, setTheme] = useStateApp(() => typeof localStorage !== "undefined" && localStorage.getItem("ds-theme") || "dark");
  const [activeNav, setActiveNav] = useStateApp("Home");
  const [chats, setChats] = useStateApp(INITIAL_CHATS);
  const [activeChat, setActiveChat] = useStateApp("1");
  const [messagesByChat, setMessagesByChat] = useStateApp(SEED_MESSAGES);
  const [typing, setTyping] = useStateApp(false);
  useEffectApp(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("ds-theme", theme);
  }, [theme]);
  const messages = messagesByChat[activeChat] || [];
  const activeChatLabel = chats.find(c => c.id === activeChat)?.label || "New conversation";
  const handleSend = text => {
    const userMsg = {
      id: Date.now(),
      role: "user",
      text
    };
    setMessagesByChat(prev => ({
      ...prev,
      [activeChat]: [...(prev[activeChat] || []), userMsg]
    }));
    setTyping(true);
    setTimeout(() => {
      const reply = AI_REPLIES[Math.floor(Math.random() * AI_REPLIES.length)];
      setMessagesByChat(prev => ({
        ...prev,
        [activeChat]: [...(prev[activeChat] || []), {
          id: Date.now() + 1,
          role: "ai",
          text: reply
        }]
      }));
      setTyping(false);
    }, 1200);
  };
  const handleNewChat = () => {
    const id = String(Date.now());
    const label = "New conversation";
    setChats(prev => [{
      id,
      label
    }, ...prev]);
    setMessagesByChat(prev => ({
      ...prev,
      [id]: []
    }));
    setActiveChat(id);
  };
  const toggleTheme = () => setTheme(t => t === "dark" ? "light" : "dark");
  return /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-ui)",
      background: "var(--bg)",
      color: "var(--text)",
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      height: 52,
      padding: "0 20px",
      borderBottom: "0.5px solid var(--border)",
      background: "var(--bg-surf)",
      gap: 20,
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement(Wordmark, null), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      display: "flex",
      alignItems: "center",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10.5,
      color: "var(--text-muted)",
      letterSpacing: 0.5
    }
  }, "v1.0 \xB7 OSS Kit"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 7
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: "var(--text-muted)"
    }
  }, theme === "dark" ? "Dark" : "Light"), /*#__PURE__*/React.createElement("button", {
    onClick: toggleTheme,
    style: {
      width: 38,
      height: 21,
      borderRadius: 11,
      background: theme === "dark" ? "var(--accent)" : "#d8dbd8",
      border: "none",
      cursor: "pointer",
      position: "relative",
      transition: "background .2s",
      padding: 0,
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 15,
      height: 15,
      borderRadius: "50%",
      background: "#fff",
      position: "absolute",
      top: 3,
      left: theme === "dark" ? 20 : 3,
      transition: "left .2s"
    }
  }))))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflow: "hidden",
      display: "flex",
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement(Sidebar, {
    chats: chats,
    activeChat: activeChat,
    onSelectChat: setActiveChat,
    onNewChat: handleNewChat,
    activeNav: activeNav,
    onNav: setActiveNav
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement(ChatHeader, {
    title: activeChatLabel
  }), /*#__PURE__*/React.createElement(MessageList, {
    messages: messages,
    showTyping: typing
  }), /*#__PURE__*/React.createElement(Composer, {
    onSend: handleSend
  })), /*#__PURE__*/React.createElement(ContextPanel, null)));
}
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(/*#__PURE__*/React.createElement(App, null));
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/App.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web/Composer.jsx
try { (() => {
/* global React, Icon */
const {
  useState: useStateCI
} = React;
function Composer({
  onSend
}) {
  const [msg, setMsg] = useStateCI("");
  const submit = () => {
    if (!msg.trim()) return;
    onSend?.(msg.trim());
    setMsg("");
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "14px 22px 18px",
      borderTop: "0.5px solid var(--border)",
      background: "var(--bg-surf)",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      border: "0.5px solid var(--border-mid)",
      borderRadius: 12,
      background: "var(--bg-panel-alt)",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("textarea", {
    value: msg,
    onChange: e => setMsg(e.target.value),
    onKeyDown: e => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submit();
      }
    },
    placeholder: "Ask anything...",
    rows: 3,
    style: {
      width: "100%",
      padding: "11px 15px 6px",
      background: "transparent",
      border: "none",
      outline: "none",
      color: "var(--text)",
      fontSize: 13,
      fontFamily: "var(--font-ui)",
      lineHeight: 1.65,
      resize: "none"
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      padding: "5px 10px 8px",
      gap: 5
    }
  }, ["M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13", "M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z", "M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"].map((p, i) => /*#__PURE__*/React.createElement("button", {
    key: i,
    className: "ds-icon-btn",
    style: {
      width: 27,
      height: 27,
      borderRadius: 7,
      background: "transparent",
      border: "0.5px solid var(--border)",
      cursor: "pointer",
      display: "flex",
      alignItems: "center",
      justifyContent: "center"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    path: p,
    size: 12,
    color: "var(--text-sub)"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10.5,
      color: "var(--text-muted)",
      fontFamily: "var(--font-ui)"
    }
  }, "claude-sonnet-4"), /*#__PURE__*/React.createElement("button", {
    onClick: submit,
    className: "ds-btn",
    style: {
      padding: "6px 15px",
      borderRadius: 8,
      background: "var(--accent)",
      border: "none",
      cursor: "pointer",
      color: "var(--accent-fg)",
      fontSize: 12,
      fontWeight: 500,
      fontFamily: "var(--font-ui)",
      display: "flex",
      alignItems: "center",
      gap: 5
    }
  }, "Send", /*#__PURE__*/React.createElement(Icon, {
    path: "M5 12h14M12 5l7 7-7 7",
    size: 12,
    color: "var(--accent-fg)",
    strokeWidth: 2
  }))))), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: "center",
      marginTop: 7,
      fontSize: 10.5,
      color: "var(--text-muted)",
      fontFamily: "var(--font-ui)"
    }
  }, "The assistant can make mistakes \xB7 Always verify important outputs"));
}
window.Composer = Composer;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/Composer.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web/ContextPanel.jsx
try { (() => {
/* global React, Icon, Mark */

function Section({
  label,
  children
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 12px",
      borderRadius: 9,
      border: "0.5px solid var(--border)",
      background: "var(--bg-panel-alt)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: "var(--text-muted)",
      letterSpacing: 1.3,
      textTransform: "uppercase",
      fontWeight: 500,
      marginBottom: 8,
      fontFamily: "var(--font-ui)"
    }
  }, label), children);
}
function ContextPanel() {
  const connectors = [{
    name: "Figma",
    status: "ok"
  }, {
    name: "Notion",
    status: "ok"
  }, {
    name: "Design tokens repo",
    status: "ok"
  }, {
    name: "Asset CDN",
    status: "warn"
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      width: 252,
      background: "var(--bg-surf)",
      borderLeft: "0.5px solid var(--border)",
      display: "flex",
      flexDirection: "column",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "13px 14px 11px",
      borderBottom: "0.5px solid var(--border)",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: "var(--text-muted)",
      letterSpacing: 1.4,
      textTransform: "uppercase",
      fontWeight: 500,
      fontFamily: "var(--font-ui)"
    }
  }, "Session Context"), /*#__PURE__*/React.createElement(Icon, {
    path: "M6 18L18 6M6 6l12 12",
    size: 12,
    color: "var(--text-muted)"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: "auto",
      padding: 10,
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(Section, {
    label: "Active Model"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 22,
      height: 22,
      borderRadius: 6,
      background: "var(--accent-bg)",
      border: "0.5px solid var(--border-strong)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center"
    }
  }, /*#__PURE__*/React.createElement(Mark, {
    size: 14
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 500,
      color: "var(--text)",
      fontFamily: "var(--font-ui)"
    }
  }, "claude-sonnet-4"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: "var(--accent)",
      fontFamily: "var(--font-ui)"
    }
  }, "200k context \xB7 streaming")))), /*#__PURE__*/React.createElement(Section, {
    label: "Context Window"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      marginBottom: 6,
      fontFamily: "var(--font-ui)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: "var(--text-sub)"
    }
  }, "Tokens used"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: "var(--text)",
      fontWeight: 500
    }
  }, "12,480 ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-muted)",
      fontWeight: 400
    }
  }, "/ 200k"))), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 3,
      borderRadius: 2,
      background: "rgba(0,0,0,0.07)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: "100%",
      width: "6.2%",
      borderRadius: 2,
      background: "var(--accent)"
    }
  }))), /*#__PURE__*/React.createElement(Section, {
    label: "Active Connectors"
  }, connectors.map((c, i) => /*#__PURE__*/React.createElement("div", {
    key: c.name,
    style: {
      display: "flex",
      alignItems: "center",
      gap: 7,
      marginBottom: i < 3 ? 5 : 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 5,
      height: 5,
      borderRadius: "50%",
      flexShrink: 0,
      background: c.status === "ok" ? "#4ade80" : "#fbbf24"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11.5,
      color: "var(--text-sub)",
      flex: 1,
      fontFamily: "var(--font-ui)"
    }
  }, c.name), c.status === "warn" && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 9.5,
      color: "#fbbf24",
      letterSpacing: 0.5,
      fontFamily: "var(--font-ui)"
    }
  }, "AUTH")))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 12px",
      borderRadius: 9,
      border: "0.5px solid var(--border-mid)",
      background: "var(--accent-bg)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: "var(--accent)",
      letterSpacing: 1.3,
      textTransform: "uppercase",
      fontWeight: 500,
      marginBottom: 9,
      fontFamily: "var(--font-ui)"
    }
  }, "Session Stats"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: "8px 12px"
    }
  }, [["Tokens In", "8,241"], ["Tokens Out", "4,239"], ["Est. Cost", "$0.023"], ["Avg Latency", "1.2s"]].map(([l, v]) => /*#__PURE__*/React.createElement("div", {
    key: l
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: "var(--text-muted)",
      marginBottom: 2,
      fontFamily: "var(--font-ui)"
    }
  }, l), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      fontWeight: 500,
      color: "var(--text)",
      fontFamily: "var(--font-ui)"
    }
  }, v)))))));
}
window.ContextPanel = ContextPanel;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/ContextPanel.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web/Messages.jsx
try { (() => {
/* global React, Icon, Mark */
const {
  useEffect: useEffectCH,
  useRef: useRefCH
} = React;
function ChatHeader({
  title,
  model = "claude-sonnet-4",
  ctx = "200k context window"
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "11px 22px",
      borderBottom: "0.5px solid var(--border)",
      display: "flex",
      alignItems: "center",
      gap: 10,
      background: "var(--bg-surf)",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 500,
      color: "var(--text)",
      fontFamily: "var(--font-ui)"
    }
  }, title), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: "var(--text-muted)",
      display: "flex",
      alignItems: "center",
      gap: 5,
      marginTop: 1,
      fontFamily: "var(--font-ui)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 5,
      height: 5,
      borderRadius: "50%",
      background: "#4ade80"
    }
  }), model, " \xB7 ", ctx)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6
    }
  }, ["M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z", "M4 6h16M4 12h16M4 18h7", "M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316"].map((p, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "ds-icon-btn",
    style: {
      width: 28,
      height: 28,
      borderRadius: 7,
      border: "0.5px solid var(--border)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      cursor: "pointer"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "13",
    height: "13",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "var(--text-sub)",
    strokeWidth: "1.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: p
  }))))));
}
function CodeBlock({
  language = "css",
  filename = "theme.css"
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 10,
      background: "rgba(0,0,0,0.28)",
      borderRadius: 8,
      padding: "10px 12px",
      borderLeft: "2px solid var(--accent)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: "var(--text-muted)",
      marginBottom: 7,
      letterSpacing: 0.5,
      fontFamily: "var(--font-mono)"
    }
  }, language, " \xB7 ", filename), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 11.5,
      lineHeight: 1.8,
      color: "#9de09d"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#c8a0f0"
    }
  }, ":root"), " ", "{", "\n", "  ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#7acce8"
    }
  }, "--accent"), ": ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#f4bb62"
    }
  }, "#21201d"), ";", "\n", "  ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#7acce8"
    }
  }, "--accent-fg"), ":  ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#f4bb62"
    }
  }, "#ffffff"), ";", "\n", "  ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#7acce8"
    }
  }, "--bg"), ":    ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "#f4bb62"
    }
  }, "#f6f5f3"), ";", "\n", "}"));
}
function Message({
  role,
  text,
  hasCode,
  index = 0
}) {
  const isUser = role === "user";
  return /*#__PURE__*/React.createElement("div", {
    className: "ds-msg-in",
    style: {
      display: "flex",
      gap: 9,
      flexDirection: isUser ? "row-reverse" : "row"
    }
  }, !isUser && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 26,
      height: 26,
      borderRadius: "50%",
      background: "var(--accent)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
      marginTop: 2
    }
  }, /*#__PURE__*/React.createElement(Mark, {
    size: 16
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "66%"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "9px 13px",
      borderRadius: isUser ? "13px 3px 13px 13px" : "3px 13px 13px 13px",
      fontSize: 13,
      lineHeight: 1.65,
      background: isUser ? "var(--user-bubble)" : "var(--ai-bubble)",
      color: isUser ? "var(--user-bubble-text)" : "var(--text)",
      border: isUser ? "none" : "0.5px solid var(--border)",
      fontFamily: "var(--font-ui)"
    }
  }, text, hasCode && /*#__PURE__*/React.createElement(CodeBlock, null)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: "var(--text-muted)",
      marginTop: 4,
      padding: "0 3px",
      fontFamily: "var(--font-ui)"
    }
  }, isUser ? "You" : "Assistant · just now")));
}
function TypingIndicator() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 9
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 26,
      height: 26,
      borderRadius: "50%",
      background: "var(--accent)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
      marginTop: 2
    }
  }, /*#__PURE__*/React.createElement(Mark, {
    size: 16
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "11px 14px",
      background: "var(--ai-bubble)",
      borderRadius: "3px 13px 13px 13px",
      border: "0.5px solid var(--border)",
      display: "flex",
      gap: 5,
      alignItems: "center"
    }
  }, [0, 1, 2].map(i => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      width: 5,
      height: 5,
      borderRadius: "50%",
      background: "var(--accent)",
      animation: "pulse 1.4s ease-in-out infinite",
      animationDelay: `${i * 0.16}s`
    }
  }))));
}
function MessageList({
  messages,
  showTyping
}) {
  const ref = useRefCH(null);
  useEffectCH(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [messages.length, showTyping]);
  return /*#__PURE__*/React.createElement("div", {
    ref: ref,
    style: {
      flex: 1,
      overflowY: "auto",
      padding: "22px",
      display: "flex",
      flexDirection: "column",
      gap: 14,
      minHeight: 0
    }
  }, messages.map((m, i) => /*#__PURE__*/React.createElement(Message, {
    key: m.id,
    role: m.role,
    text: m.text,
    hasCode: m.hasCode,
    index: i
  })), showTyping && /*#__PURE__*/React.createElement(TypingIndicator, null));
}
Object.assign(window, {
  ChatHeader,
  Message,
  MessageList,
  TypingIndicator
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/Messages.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web/Primitives.jsx
try { (() => {
/* global React */
const {
  useState
} = React;
const NAV_ICONS = {
  Home: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
  Workspace: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
  Models: "M12 2a5 5 0 110 10A5 5 0 0112 2zM5 20a7 7 0 0114 0",
  Memory: "M4 6h16M4 12h16M4 18h16",
  Connectors: "M13 2L3 14h9l-1 8 10-12h-9l1-8z"
};
function Icon({
  path,
  size = 14,
  strokeWidth = 1.5,
  color = "currentColor"
}) {
  return /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: color,
    strokeWidth: strokeWidth,
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: path
  }));
}
function Mark({
  size = 26
}) {
  return /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size,
    viewBox: "0 0 28 28",
    fill: "none"
  }, /*#__PURE__*/React.createElement("rect", {
    width: "28",
    height: "28",
    rx: "7",
    fill: "var(--accent)"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "14",
    cy: "14",
    r: "5",
    fill: "var(--accent-fg)"
  }));
}
function Wordmark() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 9
    }
  }, /*#__PURE__*/React.createElement(Mark, {
    size: 26
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 19,
      fontWeight: 600,
      letterSpacing: -0.5,
      color: "var(--text)"
    }
  }, "Acme"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 9,
      color: "var(--text-muted)",
      fontWeight: 500,
      letterSpacing: 2,
      textTransform: "uppercase",
      opacity: 0.9
    }
  }, "OSS"));
}
function Avatar({
  initials = "J",
  size = 28
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      width: size,
      height: size,
      borderRadius: "50%",
      background: "var(--accent-bg)",
      border: "1px solid var(--border-mid)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: size * 0.4,
      fontWeight: 500,
      color: "var(--accent)",
      fontFamily: "var(--font-ui)"
    }
  }, initials));
}
function Badge({
  kind = "active",
  children
}) {
  const styles = {
    active: {
      bg: "var(--accent-bg)",
      color: "var(--accent)",
      border: "var(--border-mid)"
    },
    beta: {
      bg: "var(--signal-info-bg)",
      color: "var(--status-info)",
      border: "var(--border-mid)"
    },
    new: {
      bg: "var(--signal-ok-bg)",
      color: "var(--status-ok)",
      border: "var(--border-mid)"
    },
    error: {
      bg: "var(--signal-err-bg)",
      color: "var(--status-err)",
      border: "var(--border-mid)"
    }
  }[kind];
  return /*#__PURE__*/React.createElement("span", {
    style: {
      padding: "3px 9px",
      borderRadius: 5,
      fontSize: 10.5,
      fontWeight: 500,
      letterSpacing: 0.3,
      fontFamily: "var(--font-ui)",
      background: styles.bg,
      color: styles.color,
      border: `0.5px solid ${styles.border}`
    }
  }, children);
}
function Button({
  kind = "primary",
  children,
  onClick
}) {
  const styles = {
    primary: {
      bg: "var(--accent)",
      color: "var(--accent-fg)",
      border: "none"
    },
    secondary: {
      bg: "transparent",
      color: "var(--text)",
      border: "0.5px solid var(--border-mid)"
    },
    ghost: {
      bg: "transparent",
      color: "var(--text-sub)",
      border: "0.5px solid var(--border)"
    },
    prestige: {
      bg: "var(--accent-bg)",
      color: "var(--accent)",
      border: "0.5px solid var(--border-mid)"
    },
    danger: {
      bg: "var(--signal-err-bg)",
      color: "var(--status-err)",
      border: "0.5px solid var(--border-mid)"
    }
  }[kind];
  return /*#__PURE__*/React.createElement("button", {
    onClick: onClick,
    className: "ds-btn",
    style: {
      padding: "7px 16px",
      borderRadius: 8,
      cursor: "pointer",
      fontSize: 12.5,
      fontWeight: 500,
      fontFamily: "var(--font-ui)",
      transition: "opacity .12s var(--ease-ui)",
      background: styles.bg,
      color: styles.color,
      border: styles.border
    }
  }, children);
}
Object.assign(window, {
  Icon,
  Mark,
  Wordmark,
  Avatar,
  Badge,
  Button,
  NAV_ICONS
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/Primitives.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web/Sidebar.jsx
try { (() => {
/* global React, Icon, Mark, Avatar, NAV_ICONS */
const {
  useState: useStateSB
} = React;
function Sidebar({
  chats,
  activeChat,
  onSelectChat,
  onNewChat,
  activeNav,
  onNav
}) {
  const navItems = [{
    key: "Home",
    path: NAV_ICONS.Home
  }, {
    key: "Workspace",
    path: NAV_ICONS.Workspace
  }, {
    key: "Models",
    path: NAV_ICONS.Models
  }, {
    key: "Memory",
    path: NAV_ICONS.Memory
  }, {
    key: "Connectors",
    path: NAV_ICONS.Connectors
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      width: 216,
      background: "var(--bg-surf)",
      borderRight: "0.5px solid var(--border)",
      display: "flex",
      flexDirection: "column",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "12px 8px 10px",
      borderBottom: "0.5px solid var(--border)"
    }
  }, navItems.map((n, i) => {
    const on = n.key === activeNav;
    return /*#__PURE__*/React.createElement("div", {
      key: n.key,
      className: "ds-nav-row",
      onClick: () => onNav?.(n.key),
      style: {
        display: "flex",
        alignItems: "center",
        gap: 9,
        padding: "6px 9px",
        borderRadius: 7,
        cursor: "pointer",
        marginBottom: 1,
        background: on ? "var(--accent-bg)" : "transparent",
        transition: "background .13s var(--ease-ui)"
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      path: n.path,
      size: 13,
      strokeWidth: on ? 1.8 : 1.5,
      color: on ? "var(--accent)" : "var(--text-muted)"
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 12.5,
        color: on ? "var(--accent)" : "var(--text-sub)",
        fontWeight: on ? 500 : 400,
        fontFamily: "var(--font-ui)"
      }
    }, n.key), on && /*#__PURE__*/React.createElement("div", {
      style: {
        marginLeft: "auto",
        width: 5,
        height: 5,
        borderRadius: "50%",
        background: "var(--accent)"
      }
    }));
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 8px 6px"
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: onNewChat,
    className: "ds-btn",
    style: {
      width: "100%",
      padding: "6px 10px",
      borderRadius: 7,
      border: "0.5px solid var(--border-mid)",
      background: "transparent",
      color: "var(--text-sub)",
      cursor: "pointer",
      fontSize: 12,
      fontFamily: "var(--font-ui)",
      display: "flex",
      alignItems: "center",
      gap: 7
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 15,
      lineHeight: 1,
      color: "var(--accent)"
    }
  }, "+"), /*#__PURE__*/React.createElement("span", null, "New conversation"))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: "auto",
      padding: "4px 8px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: "var(--text-muted)",
      letterSpacing: 1.4,
      textTransform: "uppercase",
      padding: "6px 5px 4px",
      fontWeight: 500,
      fontFamily: "var(--font-ui)"
    }
  }, "Recent"), chats.map(c => {
    const on = c.id === activeChat;
    return /*#__PURE__*/React.createElement("div", {
      key: c.id,
      className: "ds-chat-row",
      onClick: () => onSelectChat(c.id),
      style: {
        padding: "6px 9px",
        borderRadius: 7,
        marginBottom: 2,
        fontSize: 12,
        color: on ? "var(--accent)" : "var(--text-sub)",
        background: on ? "var(--accent-bg)" : "transparent",
        display: "flex",
        alignItems: "center",
        gap: 7,
        cursor: "pointer",
        transition: "background .13s var(--ease-ui)",
        fontFamily: "var(--font-ui)"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: 4,
        height: 4,
        borderRadius: "50%",
        background: on ? "var(--accent)" : "var(--text-muted)",
        flexShrink: 0
      }
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap"
      }
    }, c.label));
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "9px 10px 12px",
      borderTop: "0.5px solid var(--border)",
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    initials: "J"
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 500,
      color: "var(--text)",
      fontFamily: "var(--font-ui)"
    }
  }, "Jordan Lee"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: "var(--accent)",
      letterSpacing: 0.2,
      fontFamily: "var(--font-ui)"
    }
  }, "Workspace \xB7 Admin")), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      cursor: "pointer"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    path: "M12 5v.01M12 12v.01M12 19v.01",
    size: 14,
    color: "var(--text-muted)",
    strokeWidth: 2.5
  }))));
}
window.Sidebar = Sidebar;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/Sidebar.jsx", error: String((e && e.message) || e) }); }

// uploads/mio-design-system.jsx
try { (() => {
const {
  useState
} = React;
const COLORS = {
  neutral: {
    950: '#141310',
    900: '#1f1d1a',
    850: '#2b2925',
    800: '#38352f',
    750: '#45413d',
    700: '#524e49',
    600: '#696560',
    500: '#87827a',
    400: '#a9a49a',
    300: '#cbc7bf',
    200: '#e0ddd7',
    100: '#eeece8',
    50: '#f6f5f3',
    0: '#ffffff'
  },
  status: {
    ok: '#2e9e5b',
    warn: '#d99411',
    error: '#d64545',
    info: '#3b82c4'
  }
};
const makeTheme = dark => ({
  bg: dark ? '#1a1916' : '#f6f5f3',
  bgSurf: dark ? '#21201d' : '#ffffff',
  bgPanel: dark ? '#26241f' : '#ffffff',
  bgPanelAlt: dark ? '#2f2c27' : '#f6f5f3',
  bgHover: dark ? '#2f2c27' : '#eeece8',
  bgActive: dark ? '#3a3732' : '#e0ddd7',
  border: dark ? 'rgba(255,255,255,0.09)' : 'rgba(20,19,16,0.10)',
  borderMid: dark ? 'rgba(255,255,255,0.15)' : 'rgba(20,19,16,0.16)',
  text: dark ? '#e8e6e1' : '#1f1d1a',
  textSub: dark ? '#a8a39a' : '#56524c',
  textMuted: dark ? '#756f66' : '#8a857c',
  accent: dark ? '#e8e6e1' : '#21201d',
  accentFg: dark ? '#1a1916' : '#ffffff',
  accentBg: dark ? 'rgba(232,230,225,0.10)' : 'rgba(31,29,26,0.06)',
  accentGlow: dark ? 'rgba(232,230,225,0.18)' : 'rgba(31,29,26,0.12)',
  statusOk: dark ? '#54c282' : '#2e9e5b',
  statusWarn: dark ? '#e0a93a' : '#d99411',
  statusInfo: dark ? '#6aa6e0' : '#3b82c4',
  statusErr: dark ? '#e06a6a' : '#d64545',
  userBubble: dark ? '#2f2c27' : '#eeece8',
  userBubbleText: dark ? '#e8e6e1' : '#1f1d1a',
  aiBubble: dark ? '#26241f' : '#ffffff'
});
const MESSAGES = [{
  id: 1,
  role: 'user',
  text: 'Can you help me design a FastAPI WebSocket service with JWT auth for the platform?'
}, {
  id: 2,
  role: 'ai',
  text: "Here's a clean implementation. I'll use jose for JWT and a connection manager for session tracking.",
  hasCode: true
}, {
  id: 3,
  role: 'user',
  text: 'How should I handle token expiration mid-session without dropping the connection?'
}, {
  id: 4,
  role: 'ai',
  text: 'Solid question. For long-lived WebSocket sessions, there are three viable strategies depending on your security posture...',
  hasCode: false
}];
const NAV = [{
  label: 'Home',
  path: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5'
}, {
  label: 'Workspace',
  path: 'M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z'
}, {
  label: 'Models',
  path: 'M12 2a5 5 0 110 10A5 5 0 0112 2zM5 20a7 7 0 0114 0'
}, {
  label: 'Memory',
  path: 'M4 6h16M4 12h16M4 18h16'
}, {
  label: 'Connectors',
  path: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z'
}];
const CHATS = [{
  label: 'FastAPI WebSocket auth',
  active: true
}, {
  label: 'Docker Compose deploy'
}, {
  label: 'Design token migration'
}, {
  label: 'CI pipeline setup'
}, {
  label: 'Realtime sync controller'
}];
function Icon({
  path,
  size = 14,
  color = 'currentColor',
  strokeWidth = 1.5
}) {
  return /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: color,
    strokeWidth: strokeWidth,
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: path
  }));
}
function Logo({
  size = 28,
  t
}) {
  return /*#__PURE__*/React.createElement("svg", {
    width: size,
    height: size,
    viewBox: "0 0 28 28",
    fill: "none"
  }, /*#__PURE__*/React.createElement("rect", {
    width: "28",
    height: "28",
    rx: "7",
    fill: "#524e49"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "14",
    cy: "14",
    r: "5",
    fill: "#f6f5f3"
  }));
}
function App() {
  const [dark, setDark] = useState(true);
  const [tab, setTab] = useState('web');
  const t = makeTheme(dark);
  const css = `
    *{box-sizing:border-box;margin:0;padding:0;}
    ::-webkit-scrollbar{width:3px;}
    ::-webkit-scrollbar-track{background:transparent;}
    ::-webkit-scrollbar-thumb{background:${dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'};border-radius:2px;}
    textarea{resize:none;}
    input::placeholder,textarea::placeholder{color:${t.textMuted};}
    @keyframes fadeUp{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:translateY(0);}}
    @keyframes pulse{0%,80%,100%{opacity:.25;transform:scale(.7)}40%{opacity:1;transform:scale(1)}}
    @media (prefers-reduced-motion: no-preference){.msg-in{animation:fadeUp .22s ease;}}
    .dot{animation:pulse 1.4s ease-in-out infinite;}
    .nav-hover:hover{background:${t.bgHover}!important;}
    .chat-row:hover{background:${t.bgHover}!important;cursor:pointer;}
    .icon-btn:hover{background:${t.bgHover}!important;}
    .tab-pill.on{background:${t.accent}!important;color:${t.accentFg}!important;}
    .tab-pill:hover:not(.on){background:${t.bgHover}!important;}
    .send:hover{opacity:.82;}
    .conn-btn:hover{background:${t.bgHover}!important;}
    .swatch:hover{transform:scale(1.06);z-index:1;}
    .comp-btn:hover{opacity:.78;}
    .desktop-nav:hover{background:${t.bgHover}!important;}
    .desktop-nav.on{background:${t.accentBg}!important;}
  `;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-ui)",
      background: t.bg,
      color: t.text,
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column'
    }
  }, /*#__PURE__*/React.createElement("style", null, css), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      height: 52,
      padding: '0 20px',
      borderBottom: `0.5px solid ${t.border}`,
      background: t.bgSurf,
      gap: 20,
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 9
    }
  }, /*#__PURE__*/React.createElement(Logo, {
    size: 26,
    t: t
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 19,
      fontWeight: 600,
      letterSpacing: .3,
      color: t.text
    }
  }, "Acme"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 9,
      color: t.textMuted,
      fontWeight: 500,
      letterSpacing: 2,
      textTransform: 'uppercase',
      opacity: .8
    }
  }, "Platform")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 3,
      background: t.bgPanelAlt,
      borderRadius: 8,
      padding: 3,
      border: `0.5px solid ${t.border}`,
      marginLeft: 8
    }
  }, [['web', 'Web App'], ['desktop', 'Desktop'], ['tokens', 'Design Tokens']].map(([v, label]) => /*#__PURE__*/React.createElement("button", {
    key: v,
    className: `tab-pill${tab === v ? ' on' : ''}`,
    onClick: () => setTab(v),
    style: {
      padding: '4px 13px',
      borderRadius: 6,
      border: 'none',
      cursor: 'pointer',
      fontSize: 11.5,
      fontWeight: 500,
      fontFamily: "var(--font-ui)",
      background: 'transparent',
      color: tab === v ? t.accentFg : t.textSub,
      transition: 'all .15s',
      letterSpacing: .2
    }
  }, label))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto',
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10.5,
      color: t.textMuted,
      letterSpacing: .5
    }
  }, "v1.0 \xB7 OSS Kit"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 7
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: t.textMuted
    }
  }, dark ? 'Dark' : 'Light'), /*#__PURE__*/React.createElement("button", {
    onClick: () => setDark(!dark),
    style: {
      width: 38,
      height: 21,
      borderRadius: 11,
      background: dark ? t.accent : COLORS.neutral[200],
      border: 'none',
      cursor: 'pointer',
      position: 'relative',
      transition: 'background .2s',
      padding: 0,
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 15,
      height: 15,
      borderRadius: '50%',
      background: '#fff',
      position: 'absolute',
      top: 3,
      left: dark ? 20 : 3,
      transition: 'left .2s'
    }
  }))))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflow: 'hidden',
      display: 'flex',
      minHeight: 0
    }
  }, tab === 'web' && /*#__PURE__*/React.createElement(WebApp, {
    t: t,
    dark: dark
  }), tab === 'desktop' && /*#__PURE__*/React.createElement(DesktopView, {
    t: t,
    dark: dark
  }), tab === 'tokens' && /*#__PURE__*/React.createElement(TokensView, {
    t: t,
    dark: dark
  })));
}

/* ─── Web App ─── */
function WebApp({
  t,
  dark
}) {
  const [msg, setMsg] = useState('');
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flex: 1,
      overflow: 'hidden',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 216,
      background: t.bgSurf,
      borderRight: `0.5px solid ${t.border}`,
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '12px 8px 10px',
      borderBottom: `0.5px solid ${t.border}`
    }
  }, NAV.map((item, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "nav-hover",
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 9,
      padding: '6px 9px',
      borderRadius: 7,
      cursor: 'pointer',
      marginBottom: 1,
      background: i === 0 ? t.accentBg : 'transparent',
      transition: 'background .13s'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    path: item.path,
    size: 13,
    color: i === 0 ? t.accent : t.textMuted,
    strokeWidth: i === 0 ? 1.8 : 1.5
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12.5,
      color: i === 0 ? t.accent : t.textSub,
      fontWeight: i === 0 ? 500 : 400
    }
  }, item.label), i === 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto',
      width: 5,
      height: 5,
      borderRadius: '50%',
      background: t.statusOk
    }
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '10px 8px 6px'
    }
  }, /*#__PURE__*/React.createElement("button", {
    style: {
      width: '100%',
      padding: '6px 10px',
      borderRadius: 7,
      border: `0.5px solid ${t.borderMid}`,
      background: 'transparent',
      color: t.textSub,
      cursor: 'pointer',
      fontSize: 12,
      fontFamily: "var(--font-ui)",
      display: 'flex',
      alignItems: 'center',
      gap: 7
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 15,
      lineHeight: 1,
      color: t.accent
    }
  }, "+"), /*#__PURE__*/React.createElement("span", null, "New conversation"))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: 'auto',
      padding: '4px 8px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: t.textMuted,
      letterSpacing: 1.4,
      textTransform: 'uppercase',
      padding: '6px 5px 4px',
      fontWeight: 500
    }
  }, "Recent"), CHATS.map((c, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "chat-row",
    style: {
      padding: '6px 9px',
      borderRadius: 7,
      marginBottom: 2,
      fontSize: 12,
      color: c.active ? t.accent : t.textSub,
      background: c.active ? t.accentBg : 'transparent',
      display: 'flex',
      alignItems: 'center',
      gap: 7,
      transition: 'background .13s'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 4,
      height: 4,
      borderRadius: '50%',
      background: c.active ? t.accent : t.textMuted,
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, c.label)))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '9px 10px 12px',
      borderTop: `0.5px solid ${t.border}`,
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 28,
      height: 28,
      borderRadius: '50%',
      background: t.accentBg,
      border: `1px solid ${t.accent}40`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      fontWeight: 600,
      color: t.accent
    }
  }, "J")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 500,
      color: t.text
    }
  }, "Jordan Lee"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: t.textMuted,
      letterSpacing: .2
    }
  }, "Workspace \xB7 Admin")), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto',
      cursor: 'pointer'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    path: "M12 5v.01M12 12v.01M12 19v.01",
    size: 14,
    color: t.textMuted,
    strokeWidth: 2.5
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '11px 22px',
      borderBottom: `0.5px solid ${t.border}`,
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      background: t.bgSurf,
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 500,
      color: t.text
    }
  }, "FastAPI WebSocket auth"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: t.textMuted,
      display: 'flex',
      alignItems: 'center',
      gap: 5,
      marginTop: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 5,
      height: 5,
      borderRadius: '50%',
      background: t.statusOk
    }
  }), "claude-sonnet-4 \xB7 200k context window")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6
    }
  }, ['M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z', 'M4 6h16M4 12h16M4 18h7', 'M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z'].map((p, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "icon-btn",
    style: {
      width: 28,
      height: 28,
      borderRadius: 7,
      border: `0.5px solid ${t.border}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: 'pointer',
      transition: 'background .13s'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    path: p,
    size: 13,
    color: t.textSub
  }))))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: 'auto',
      padding: '22px',
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
      minHeight: 0
    }
  }, MESSAGES.map((m, i) => /*#__PURE__*/React.createElement("div", {
    key: m.id,
    className: "msg-in",
    style: {
      display: 'flex',
      gap: 9,
      flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
      animationDelay: `${i * .07}s`
    }
  }, m.role === 'ai' && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 26,
      height: 26,
      borderRadius: '50%',
      background: 'transparent',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
      marginTop: 2
    }
  }, /*#__PURE__*/React.createElement(Logo, {
    size: 16
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: '66%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '9px 13px',
      borderRadius: m.role === 'user' ? '13px 3px 13px 13px' : '3px 13px 13px 13px',
      fontSize: 13,
      lineHeight: 1.65,
      background: m.role === 'user' ? t.userBubble : t.aiBubble,
      color: m.role === 'user' ? t.userBubbleText : t.text,
      border: m.role === 'ai' ? `0.5px solid ${t.border}` : 'none'
    }
  }, m.text, m.hasCode && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 10,
      background: dark ? 'rgba(0,0,0,0.28)' : 'rgba(52,71,52,0.05)',
      borderRadius: 8,
      padding: '10px 12px',
      borderLeft: `2px solid ${t.accent}`
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: t.textMuted,
      marginBottom: 7,
      letterSpacing: .5
    }
  }, "python \xB7 ws_service.py"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'monospace',
      fontSize: 11.5,
      lineHeight: 1.8,
      color: dark ? '#9de09d' : '#2a4a2a'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: dark ? '#7acce8' : '#1a5a7a'
    }
  }, "from "), "fastapi ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: dark ? '#7acce8' : '#1a5a7a'
    }
  }, "import "), "FastAPI, WebSocket", '\n', /*#__PURE__*/React.createElement("span", {
    style: {
      color: dark ? '#7acce8' : '#1a5a7a'
    }
  }, "from "), "jose ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: dark ? '#7acce8' : '#1a5a7a'
    }
  }, "import "), "JWTError, jwt", '\n', '\n', /*#__PURE__*/React.createElement("span", {
    style: {
      color: dark ? '#c8a0f0' : '#6a3a9a'
    }
  }, "async def "), /*#__PURE__*/React.createElement("span", {
    style: {
      color: dark ? '#9de09d' : '#2a7a2a'
    }
  }, "authenticate_ws"), "(token: str):", '\n', '    ', /*#__PURE__*/React.createElement("span", {
    style: {
      color: dark ? '#7acce8' : '#1a5a7a'
    }
  }, "try"), ":", '\n', '        ', "payload = jwt.decode(token, SECRET_KEY)"))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: t.textMuted,
      marginTop: 4,
      padding: '0 3px'
    }
  }, m.role === 'ai' ? 'Assistant · just now' : 'You')))), /*#__PURE__*/React.createElement("div", {
    className: "msg-in",
    style: {
      display: 'flex',
      gap: 9,
      animationDelay: '.28s'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 26,
      height: 26,
      borderRadius: '50%',
      background: 'transparent',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
      marginTop: 2
    }
  }, /*#__PURE__*/React.createElement(Logo, {
    size: 16
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '11px 14px',
      background: t.aiBubble,
      borderRadius: '3px 13px 13px 13px',
      border: `0.5px solid ${t.border}`,
      display: 'flex',
      gap: 5,
      alignItems: 'center'
    }
  }, [0, 1, 2].map(i => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "dot",
    style: {
      width: 5,
      height: 5,
      borderRadius: '50%',
      background: t.accent,
      animationDelay: `${i * .16}s`
    }
  }))))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '14px 22px 18px',
      borderTop: `0.5px solid ${t.border}`,
      background: t.bgSurf,
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      border: `0.5px solid ${t.borderMid}`,
      borderRadius: 12,
      background: dark ? t.bgPanelAlt : t.bgSurf,
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("textarea", {
    value: msg,
    onChange: e => setMsg(e.target.value),
    placeholder: "Ask anything...",
    rows: 3,
    style: {
      width: '100%',
      padding: '11px 15px 6px',
      background: 'transparent',
      border: 'none',
      outline: 'none',
      color: t.text,
      fontSize: 13,
      fontFamily: "var(--font-ui)",
      lineHeight: 1.65
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      padding: '5px 10px 8px',
      gap: 5
    }
  }, ['M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13', 'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z', 'M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4'].map((p, i) => /*#__PURE__*/React.createElement("button", {
    key: i,
    className: "icon-btn",
    style: {
      width: 27,
      height: 27,
      borderRadius: 7,
      background: 'transparent',
      border: `0.5px solid ${t.border}`,
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'background .13s'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    path: p,
    size: 12,
    color: t.textSub
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto',
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10.5,
      color: t.textMuted
    }
  }, "claude-sonnet-4"), /*#__PURE__*/React.createElement("button", {
    className: "send",
    style: {
      padding: '6px 15px',
      borderRadius: 8,
      background: t.accent,
      border: 'none',
      cursor: 'pointer',
      color: t.accentFg,
      fontSize: 12,
      fontWeight: 500,
      fontFamily: "var(--font-ui)",
      display: 'flex',
      alignItems: 'center',
      gap: 5,
      transition: 'opacity .15s'
    }
  }, "Send", /*#__PURE__*/React.createElement(Icon, {
    path: "M5 12h14M12 5l7 7-7 7",
    size: 12,
    color: t.accentFg,
    strokeWidth: 2
  }))))), /*#__PURE__*/React.createElement("div", {
    style: {
      textAlign: 'center',
      marginTop: 7,
      fontSize: 10.5,
      color: t.textMuted
    }
  }, "The assistant can make mistakes \xB7 Always verify important outputs"))), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 252,
      background: t.bgSurf,
      borderLeft: `0.5px solid ${t.border}`,
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '13px 14px 11px',
      borderBottom: `0.5px solid ${t.border}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: t.textMuted,
      letterSpacing: 1.4,
      textTransform: 'uppercase',
      fontWeight: 500
    }
  }, "Session Context"), /*#__PURE__*/React.createElement(Icon, {
    path: "M6 18L18 6M6 6l12 12",
    size: 12,
    color: t.textMuted
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: 'auto',
      padding: '10px',
      display: 'flex',
      flexDirection: 'column',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(ContextCard, {
    t: t,
    dark: dark,
    label: "Active Model"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 22,
      height: 22,
      borderRadius: 6,
      background: t.accentBg,
      border: `0.5px solid ${t.accent}30`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement(Logo, {
    size: 14
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 500,
      color: t.text
    }
  }, "claude-sonnet-4"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: t.textMuted
    }
  }, "200k context \xB7 streaming")))), /*#__PURE__*/React.createElement(ContextCard, {
    t: t,
    dark: dark,
    label: "Context Window"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: t.textSub
    }
  }, "Tokens used"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: t.text,
      fontWeight: 500
    }
  }, "12,480 ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: t.textMuted,
      fontWeight: 400
    }
  }, "/ 200k"))), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 3,
      borderRadius: 2,
      background: dark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      width: '6.2%',
      borderRadius: 2,
      background: t.accent
    }
  }))), /*#__PURE__*/React.createElement(ContextCard, {
    t: t,
    dark: dark,
    label: "Active Connectors"
  }, [{
    name: 'GitHub',
    status: 'ok'
  }, {
    name: 'Linear',
    status: 'ok'
  }, {
    name: 'Figma',
    status: 'ok'
  }, {
    name: 'Vercel',
    status: 'warn'
  }].map((conn, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 7,
      marginBottom: i < 3 ? 5 : 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 5,
      height: 5,
      borderRadius: '50%',
      background: conn.status === 'ok' ? t.statusOk : t.statusWarn,
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11.5,
      color: t.textSub,
      flex: 1
    }
  }, conn.name), conn.status === 'warn' && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 9.5,
      color: t.statusWarn,
      letterSpacing: .5
    }
  }, "AUTH")))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '10px 12px',
      borderRadius: 9,
      border: `0.5px solid ${t.border}`,
      background: t.accentBg
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: t.textMuted,
      letterSpacing: 1.3,
      textTransform: 'uppercase',
      fontWeight: 500,
      marginBottom: 9
    }
  }, "Session Stats"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: '8px 12px'
    }
  }, [['Tokens In', '8,241'], ['Tokens Out', '4,239'], ['Est. Cost', '$0.023'], ['Avg Latency', '1.2s']].map(([l, v]) => /*#__PURE__*/React.createElement("div", {
    key: l
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: t.textMuted,
      marginBottom: 2
    }
  }, l), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      fontWeight: 500,
      color: t.text
    }
  }, v))))))));
}
function ContextCard({
  t,
  dark,
  label,
  children
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '10px 12px',
      borderRadius: 9,
      border: `0.5px solid ${t.border}`,
      background: dark ? t.bgPanelAlt : t.bg
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: t.textMuted,
      letterSpacing: 1.3,
      textTransform: 'uppercase',
      fontWeight: 500,
      marginBottom: 8
    }
  }, label), children);
}

/* ─── Desktop Companion ─── */
function DesktopView({
  t,
  dark
}) {
  const [activeNav, setActiveNav] = useState(0);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 32,
      background: dark ? COLORS.neutral[950] : COLORS.neutral[100],
      flexDirection: 'column',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 400,
      height: 560,
      borderRadius: 14,
      overflow: 'hidden',
      border: `0.5px solid ${t.borderMid}`,
      display: 'flex',
      flexDirection: 'column',
      background: t.bgSurf
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 34,
      background: dark ? COLORS.neutral[900] : '#e8eae8',
      display: 'flex',
      alignItems: 'center',
      padding: '0 12px',
      gap: 6,
      borderBottom: `0.5px solid ${t.border}`,
      flexShrink: 0
    }
  }, ['#ff5f57', '#febc2e', '#28c840'].map((c, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      width: 10,
      height: 10,
      borderRadius: '50%',
      background: c
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      textAlign: 'center',
      fontSize: 11,
      color: t.textMuted,
      letterSpacing: .3
    }
  }, "Acme \u2014 Desktop"), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 12,
      height: 12,
      borderRadius: 3,
      border: `0.5px solid ${t.border}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    path: "M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3",
    size: 8,
    color: t.textMuted,
    strokeWidth: 1.5
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      overflow: 'hidden',
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 48,
      background: dark ? COLORS.neutral[900] : COLORS.neutral[50],
      borderRight: `0.5px solid ${t.border}`,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '10px 0',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 26,
      height: 26,
      borderRadius: 7,
      background: 'transparent',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement(Logo, {
    size: 16
  })), NAV.map((item, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: `desktop-nav${activeNav === i ? ' on' : ''}`,
    onClick: () => setActiveNav(i),
    style: {
      width: 34,
      height: 34,
      borderRadius: 8,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: 'pointer',
      transition: 'background .13s',
      background: activeNav === i ? t.accentBg : 'transparent'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    path: item.path,
    size: 13,
    color: activeNav === i ? t.accent : t.textMuted,
    strokeWidth: activeNav === i ? 1.8 : 1.5
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 'auto',
      width: 26,
      height: 26,
      borderRadius: '50%',
      background: t.accentBg,
      border: `1px solid ${t.accent}30`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      fontWeight: 600,
      color: t.accent
    }
  }, "J"))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 13px',
      borderBottom: `0.5px solid ${t.border}`,
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 500,
      color: t.text
    }
  }, "FastAPI WebSocket auth"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      color: t.textMuted,
      display: 'flex',
      alignItems: 'center',
      gap: 4,
      marginTop: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 4,
      height: 4,
      borderRadius: '50%',
      background: t.statusOk
    }
  }), "claude-sonnet-4")), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: 'auto',
      padding: '11px 12px',
      display: 'flex',
      flexDirection: 'column',
      gap: 9,
      minHeight: 0
    }
  }, MESSAGES.slice(0, 3).map((m, i) => /*#__PURE__*/React.createElement("div", {
    key: m.id,
    className: "msg-in",
    style: {
      display: 'flex',
      gap: 6,
      flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
      animationDelay: `${i * .06}s`
    }
  }, m.role === 'ai' && /*#__PURE__*/React.createElement("div", {
    style: {
      width: 20,
      height: 20,
      borderRadius: '50%',
      background: 'transparent',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
      marginTop: 1
    }
  }, /*#__PURE__*/React.createElement(Logo, {
    size: 13
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: '76%',
      padding: '7px 10px',
      borderRadius: m.role === 'user' ? '10px 3px 10px 10px' : '3px 10px 10px 10px',
      fontSize: 11.5,
      lineHeight: 1.6,
      background: m.role === 'user' ? t.userBubble : t.aiBubble,
      color: m.role === 'user' ? t.userBubbleText : t.text,
      border: m.role === 'ai' ? `0.5px solid ${t.border}` : 'none'
    }
  }, m.text.length > 75 ? m.text.slice(0, 75) + '…' : m.text))), /*#__PURE__*/React.createElement("div", {
    className: "msg-in",
    style: {
      display: 'flex',
      gap: 6,
      animationDelay: '.18s'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 20,
      height: 20,
      borderRadius: '50%',
      background: 'transparent',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
      marginTop: 1
    }
  }, /*#__PURE__*/React.createElement(Logo, {
    size: 13
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '9px 12px',
      background: t.aiBubble,
      borderRadius: '3px 10px 10px 10px',
      border: `0.5px solid ${t.border}`,
      display: 'flex',
      gap: 4,
      alignItems: 'center'
    }
  }, [0, 1, 2].map(i => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "dot",
    style: {
      width: 4,
      height: 4,
      borderRadius: '50%',
      background: t.accent,
      animationDelay: `${i * .14}s`
    }
  }))))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '8px 10px 10px',
      borderTop: `0.5px solid ${t.border}`,
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 5,
      alignItems: 'center',
      padding: '6px 9px',
      borderRadius: 8,
      border: `0.5px solid ${t.borderMid}`,
      background: dark ? t.bgPanelAlt : t.bg
    }
  }, /*#__PURE__*/React.createElement("input", {
    placeholder: "Ask anything...",
    style: {
      flex: 1,
      background: 'transparent',
      border: 'none',
      outline: 'none',
      color: t.text,
      fontSize: 12,
      fontFamily: "var(--font-ui)"
    }
  }), /*#__PURE__*/React.createElement("button", {
    style: {
      width: 22,
      height: 22,
      borderRadius: 6,
      background: t.accent,
      border: 'none',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    path: "M5 12h14M12 5l7 7-7 7",
    size: 10,
    color: t.accentFg,
    strokeWidth: 2
  }))))))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: t.textMuted,
      letterSpacing: .4
    }
  }, "Desktop Companion \xB7 Compact floating window \xB7 macOS / Windows / Linux"));
}

/* ─── Design Tokens ─── */
function TokensView({
  t,
  dark
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: 'auto',
      padding: '32px 36px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: 860,
      margin: '0 auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 36
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 40,
      fontWeight: 500,
      color: t.text,
      letterSpacing: -.5,
      lineHeight: 1.05
    }
  }, "Design Tokens"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      color: t.textSub,
      marginTop: 8,
      lineHeight: 1.65
    }
  }, "The visual foundation \u2014 color, typography, spacing, and component anatomy.")), /*#__PURE__*/React.createElement(Section, {
    t: t,
    label: "Color System"
  }, [{
    name: 'Neutral · warm gray',
    scale: COLORS.neutral
  }, {
    name: 'Status signals',
    scale: COLORS.status
  }].map(({
    name,
    scale
  }) => /*#__PURE__*/React.createElement("div", {
    key: name,
    style: {
      marginBottom: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: t.textSub,
      marginBottom: 7,
      fontWeight: 500
    }
  }, name), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 3
    }
  }, Object.entries(scale).map(([stop, hex]) => /*#__PURE__*/React.createElement("div", {
    key: stop,
    className: "swatch",
    style: {
      flex: 1,
      cursor: 'default',
      transition: 'transform .13s',
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("div", {
    title: hex,
    style: {
      height: 36,
      borderRadius: 5,
      background: hex,
      border: stop === '0' ? `0.5px solid ${t.border}` : 'none'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 8.5,
      color: t.textMuted,
      marginTop: 3,
      textAlign: 'center',
      letterSpacing: .2
    }
  }, stop))))))), /*#__PURE__*/React.createElement(Section, {
    t: t,
    label: "Semantic Tokens (Active Theme)"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill,minmax(185px,1fr))',
      gap: 8
    }
  }, [{
    k: 'Background',
    v: t.bg
  }, {
    k: 'Surface',
    v: t.bgSurf
  }, {
    k: 'Panel',
    v: t.bgPanel
  }, {
    k: 'Border',
    v: dark ? 'rgba(255,255,255,0.065)' : 'var(--border)'
  }, {
    k: 'Text Primary',
    v: t.text
  }, {
    k: 'Text Secondary',
    v: t.textSub
  }, {
    k: 'Accent',
    v: t.accent
  }, {
    k: 'Accent Foreground',
    v: t.accentFg
  }, {
    k: 'Accent Background',
    v: t.accentBg
  }, {
    k: 'User Bubble',
    v: t.userBubble
  }, {
    k: 'AI Bubble',
    v: t.aiBubble
  }].map(tok => /*#__PURE__*/React.createElement("div", {
    key: tok.k,
    style: {
      padding: '9px 11px',
      borderRadius: 8,
      border: `0.5px solid ${t.border}`,
      background: dark ? t.bgPanelAlt : t.bg
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 7,
      marginBottom: 5
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 18,
      height: 18,
      borderRadius: 4,
      background: tok.v,
      border: `0.5px solid ${t.border}`,
      flexShrink: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11.5,
      fontWeight: 500,
      color: t.text
    }
  }, tok.k)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      color: t.textMuted,
      fontFamily: 'monospace'
    }
  }, tok.v))))), /*#__PURE__*/React.createElement(Section, {
    t: t,
    label: "Typography System"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '24px',
      borderRadius: 11,
      border: `0.5px solid ${t.border}`,
      background: dark ? t.bgPanelAlt : t.bg
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 46,
      fontWeight: 600,
      color: t.text,
      lineHeight: 1.05,
      letterSpacing: -.5,
      marginBottom: 2
    }
  }, "Acme Platform"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 22,
      fontWeight: 400,
      fontStyle: 'italic',
      color: t.textSub,
      marginBottom: 22
    }
  }, "Intelligent companion for the modern workflow"), /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: `0.5px solid ${t.border}`,
      paddingTop: 16,
      display: 'flex',
      flexDirection: 'column',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(TypeRow, {
    label: "Display \xB7 System sans 600",
    sample: "Section Heading",
    size: 20,
    t: t,
    serif: true
  }), /*#__PURE__*/React.createElement(TypeRow, {
    label: "Heading \xB7 System sans 600, 16px",
    sample: "Card and panel headings",
    size: 16,
    t: t,
    bold: true
  }), /*#__PURE__*/React.createElement(TypeRow, {
    label: "Body \xB7 System sans 400, 13.5px / 1.65",
    sample: "Primary interface text for messages and content",
    size: 13.5,
    t: t
  }), /*#__PURE__*/React.createElement(TypeRow, {
    label: "Caption \xB7 System sans 500, 9.5px, tracked uppercase",
    sample: "SECTION LABELS",
    size: 9.5,
    t: t,
    upper: true,
    bold: true
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      color: t.textMuted
    }
  }, "Mono \xB7"), /*#__PURE__*/React.createElement("code", {
    style: {
      fontSize: 12,
      fontFamily: 'monospace',
      color: t.accent,
      background: t.accentBg,
      padding: '3px 9px',
      borderRadius: 5
    }
  }, "await websocket.accept()"))))), /*#__PURE__*/React.createElement(Section, {
    t: t,
    label: "Component Library"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '22px',
      borderRadius: 11,
      border: `0.5px solid ${t.border}`,
      background: dark ? t.bgPanelAlt : t.bg,
      display: 'flex',
      flexWrap: 'wrap',
      gap: 10,
      alignItems: 'center'
    }
  }, [{
    label: 'Primary',
    bg: t.accent,
    color: t.accentFg,
    border: 'none'
  }, {
    label: 'Secondary',
    bg: 'transparent',
    color: t.text,
    border: `0.5px solid ${t.borderMid}`
  }, {
    label: 'Ghost',
    bg: 'transparent',
    color: t.textSub,
    border: `0.5px solid ${t.border}`
  }, {
    label: 'Soft',
    bg: t.accentBg,
    color: t.accent,
    border: `0.5px solid ${t.borderMid}`
  }, {
    label: 'Danger',
    bg: 'rgba(214,69,69,0.12)',
    color: t.statusErr,
    border: `0.5px solid ${t.borderMid}`
  }].map(b => /*#__PURE__*/React.createElement("button", {
    key: b.label,
    className: "comp-btn",
    style: {
      padding: '7px 16px',
      borderRadius: 7,
      border: b.border,
      cursor: 'pointer',
      background: b.bg,
      color: b.color,
      fontSize: 12.5,
      fontWeight: 500,
      fontFamily: "var(--font-ui)",
      transition: 'opacity .15s'
    }
  }, b.label)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 5,
      flexWrap: 'wrap'
    }
  }, [{
    l: 'active',
    bg: t.accentBg,
    c: t.accent,
    bd: `0.5px solid ${t.borderMid}`
  }, {
    l: 'beta',
    bg: 'rgba(59,130,196,0.12)',
    c: t.statusInfo,
    bd: `0.5px solid ${t.borderMid}`
  }, {
    l: 'new',
    bg: 'rgba(46,158,91,0.12)',
    c: t.statusOk,
    bd: `0.5px solid ${t.borderMid}`
  }, {
    l: 'error',
    bg: 'rgba(214,69,69,0.12)',
    c: t.statusErr,
    bd: `0.5px solid ${t.borderMid}`
  }].map(badge => /*#__PURE__*/React.createElement("span", {
    key: badge.l,
    style: {
      padding: '3px 9px',
      borderRadius: 5,
      fontSize: 10.5,
      fontWeight: 500,
      letterSpacing: .3,
      background: badge.bg,
      color: badge.c,
      border: badge.bd
    }
  }, badge.l))))), /*#__PURE__*/React.createElement(Section, {
    t: t,
    label: "Spacing Scale"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '20px',
      borderRadius: 11,
      border: `0.5px solid ${t.border}`,
      background: dark ? t.bgPanelAlt : t.bg
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      alignItems: 'flex-end',
      flexWrap: 'wrap'
    }
  }, [4, 8, 12, 16, 20, 24, 32, 40, 48, 64].map(n => /*#__PURE__*/React.createElement("div", {
    key: n,
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 5
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: Math.min(n, 48),
      height: Math.min(n, 48),
      borderRadius: 3,
      background: t.accent,
      opacity: .3 + n / 128
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 9,
      color: t.textMuted
    }
  }, n, "px")))))), /*#__PURE__*/React.createElement(Section, {
    t: t,
    label: "Border Radius"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '20px',
      borderRadius: 11,
      border: `0.5px solid ${t.border}`,
      background: dark ? t.bgPanelAlt : t.bg
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 12,
      alignItems: 'flex-end',
      flexWrap: 'wrap'
    }
  }, [{
    r: 3,
    l: 'sm'
  }, {
    r: 6,
    l: 'xs'
  }, {
    r: 8,
    l: 'md'
  }, {
    r: 10,
    l: 'lg'
  }, {
    r: 12,
    l: 'xl'
  }, {
    r: 16,
    l: '2xl'
  }, {
    r: 999,
    l: 'full'
  }].map(({
    r,
    l
  }) => /*#__PURE__*/React.createElement("div", {
    key: l,
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 44,
      height: 44,
      borderRadius: r,
      background: t.accentBg,
      border: `0.5px solid ${t.accent}40`
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 9.5,
      color: t.textMuted
    }
  }, l), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 8.5,
      color: t.textMuted,
      fontFamily: 'monospace'
    }
  }, r === 999 ? '50%' : r + 'px'))))))));
}
function Section({
  t,
  label,
  children
}) {
  return /*#__PURE__*/React.createElement("section", {
    style: {
      marginBottom: 36
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 9.5,
      letterSpacing: 1.5,
      textTransform: 'uppercase',
      color: t.textMuted,
      fontWeight: 500,
      marginBottom: 14
    }
  }, label), children);
}
function TypeRow({
  label,
  sample,
  size,
  t,
  serif,
  bold,
  upper
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: serif ? "var(--font-display)" : "var(--font-ui)",
      fontSize: size,
      fontWeight: bold ? 500 : 400,
      color: t.text,
      textTransform: upper ? 'uppercase' : undefined,
      letterSpacing: upper ? 1.2 : undefined,
      flexShrink: 0
    }
  }, sample), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 10,
      color: t.textMuted
    }
  }, label));
}
Object.assign(__ds_scope, { App });
})(); } catch (e) { __ds_ns.__errors.push({ path: "uploads/mio-design-system.jsx", error: String((e && e.message) || e) }); }

__ds_ns.App = __ds_scope.App;

})();
