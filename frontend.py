import os
import re
import requests
import streamlit as st
import streamlit.components.v1 as components
import markdown

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="עוזר שירותים רפואיים", page_icon="💬", layout="wide")

# ---- Layout constants ----
CHAT_WIDTH_PX = 760          # width of chat pane (input matches this)
TYPING_MARKER = "__TYPING__"  # internal placeholder for typing bubble


# --------- Markdown rendering (safe-ish) ----------
def render_markdown_safe(text: str) -> str:
    """
    Convert Markdown to HTML (bold/italic/lists/links) and strip dangerous HTML.
    This lets **bold**, *italic*, bullet lists, and links render nicely in bubbles.
    """
    html_out = markdown.markdown(
        text or "",
        extensions=["extra", "nl2br", "sane_lists"],
        output_format="xhtml",
    )
    # Strip <script> / <iframe> and inline event handlers like onclick=
    html_out = re.sub(r"(?is)<script.*?>.*?</script>", "", html_out)
    html_out = re.sub(r"(?is)<iframe.*?>.*?</iframe>", "", html_out)
    html_out = re.sub(r"\son\w+\s*=\s*(['\"]).*?\1", "", html_out)  # remove onX="..."
    # Block javascript: URLs
    html_out = re.sub(
        r'href\s*=\s*([\'"])\s*javascript:[^\'"]*\1', r'href="#"', html_out, flags=re.I
    )
    return html_out


# ===== Styles (RTL + bubbles + avatars + centered input) =====
st.markdown(
    f"""
    <style>
      /* RTL base */
      html, body, .stApp, .block-container, section.main {{ direction: rtl; }}

      /* Centered title */
      h1 {{ text-align: center; }}

      /* Center the "New Chat" button row */
      .new-chat-wrap {{ display: flex; justify-content: center; margin-bottom: 0.25rem; }}

      /* Chat pane centered */
      #chat-pane {{ width: {CHAT_WIDTH_PX}px; max-width: 95vw; margin: 0 auto; }}

      /* Rows with neutral gap so RTL item order controls avatar side */
      .row {{
        display: flex;
        align-items: flex-end;
        margin: 8px 0 14px 0;
        gap: 8px;  /* spacing between bubble and avatar */
      }}
      .row.user      {{ justify-content: flex-end; }}   /* user messages right-aligned */
      .row.assistant {{ justify-content: flex-start; }} /* assistant messages left-aligned */

      /* Avatars */
      .avatar {{
        width: 36px; height: 36px; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 18px; box-shadow: 0 2px 6px rgba(0,0,0,0.18);
        user-select: none;
      }}
      .avatar.user {{ background: #244fca; color: #fff; }}
      .avatar.assistant {{ background: #1f1f1f; color: #eaeaea; }}

      /* Bubbles */
      .bubble {{
        display: inline-block;
        padding: 12px 16px;
        border-radius: 16px;
        line-height: 1.55;
        word-wrap: break-word;
        box-shadow: 0 2px 6px rgba(0,0,0,0.18);
        font-size: 1.02rem;
        max-width: 90%;
        text-align: right;  /* natural for Hebrew */
      }}
      .bubble.user {{
        background: #2f6fef;
        color: #ffffff;
        border-top-right-radius: 6px;
      }}
      .bubble.assistant {{
        background: #2a2a2a;
        color: #f5f5f5;
        border-top-left-radius: 6px;
      }}
      .bubble p {{ margin: 0.25rem 0; }}
      .bubble ul, .bubble ol {{ margin: 0.35rem 1.25rem 0.35rem 0; }}
      .bubble li {{ margin: 0.2rem 0; }}

      /* Typing bubble (animated three dots) */
      .typing-bubble {{ padding: 10px 14px; }}
      .typing {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
      }}
      .typing span {{
        width: 6px; height: 6px;
        background: #e6e6e6; border-radius: 50%;
        opacity: 0.2; animation: blink 1.3s infinite ease-in-out;
      }}
      .typing span:nth-child(2) {{ animation-delay: .15s; }}
      .typing span:nth-child(3) {{ animation-delay: .30s; }}
      @keyframes blink {{
        0%   {{ opacity: .2; transform: translateY(0); }}
        20%  {{ opacity: .6; transform: translateY(-2px); }}
        40%  {{ opacity: 1;  transform: translateY(0); }}
        100% {{ opacity: .2; transform: translateY(0); }}
      }}

      /* Hide Streamlit built-in chat avatars/actions (we render our own) */
      [data-testid="stChatMessageAvatar"], [data-testid="stChatMessageActions"] {{ display: none !important; }}

      /* Chat input: exactly CHAT_WIDTH_PX, centered, with grey wrapper */
      [data-testid="stChatInput"] {{
        display: block;
        width: {CHAT_WIDTH_PX}px !important;
        max-width: 95vw;
        margin-left: auto !important;
        margin-right: auto !important;
        background: transparent;
        border: none !important;
        background-color: #2b2b2b;
      }}
      [data-testid="stChatInput"] > div {{
        width: 100%;
        margin: 0 auto !important;
      }}
      [data-testid="stChatInput"] form {{
        width: 100%;
        background-color: #2b2b2b;  /* grey-like */
        border-radius: 10px;
        padding: 6px 10px;
        border: 1px solid #444;
      }}
      [data-testid="stChatInput"] textarea {{
        width: 100% !important;
        box-sizing: border-box !important;
        direction: rtl;
        text-align: right;
        font-size: 1rem;
        background: transparent !important;
        color: #f5f5f5;
        border: none !important;
        outline: none !important;
        resize: none !important;
      }}
      [data-testid="stChatInput"] :focus,
      [data-testid="stChatInput"] :focus-visible {{
        outline: none !important;
        box-shadow: none !important;
      }}

      .block-container {{ padding-top: 1.25rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ===== Session state =====
if "messages" not in st.session_state:
    st.session_state.messages = []          # [{role: "user"|"assistant", "content": str}]
if "profile" not in st.session_state:
    st.session_state.profile = {}
if "language_hint" not in st.session_state:
    st.session_state.language_hint = None
if "used_snippets" not in st.session_state:
    st.session_state.used_snippets = []
if "phase" not in st.session_state:
    st.session_state.phase = "collect"      # switches to "qa" after confirmation
if "last_rendered_count" not in st.session_state:
    st.session_state.last_rendered_count = 0
if "greeted" not in st.session_state:
    st.session_state.greeted = False


# ===== HTML builder =====
def build_chat_html() -> str:
    parts = ['<div id="chat-pane">']
    for m in st.session_state.messages:
        role = "user" if m["role"] == "user" else "assistant"
        text = m["content"]

        # Friendlier confirmation copy on client
        if isinstance(text, str) and text.strip().startswith("✅ הפרופיל אושר"):
            text = "מעולה! אישרתי את הפרטים 🙂\nמה תרצה לדעת?"

        # Assistant typing bubble (avatar on the RIGHT in RTL)
        if text == TYPING_MARKER:
            parts.append(
                '<div class="row assistant">'
                '  <div class="avatar assistant" title="העוזר">🤖</div>'
                '  <div class="bubble assistant typing-bubble">'
                '    <div class="typing" aria-live="polite" aria-label="העוזר מקליד">'
                '      <span></span><span></span><span></span>'
                '    </div>'
                '  </div>'
                '</div>'
            )
            continue

        html_safe = render_markdown_safe(str(text))

        if role == "user":
            # Bubble first, then avatar -> avatar ends up on the LEFT (RTL)
            parts.append(
                '<div class="row user">'
                f'  <div class="bubble user">{html_safe}</div>'
                '  <div class="avatar user" title="משתמש">👤</div>'
                '</div>'
            )
        else:
            # Avatar first, then bubble -> avatar ends up on the RIGHT (RTL)
            parts.append(
                '<div class="row assistant">'
                '  <div class="avatar assistant" title="העוזר">🤖</div>'
                f'  <div class="bubble assistant">{html_safe}</div>'
                '</div>'
            )
    parts.append("</div>")
    return "\n".join(parts)


def render_chat_into(container):
    container.markdown(build_chat_html(), unsafe_allow_html=True)


def auto_scroll_to_bottom():
    components.html(
        """
        <script>
          const doc = window.parent.document;
          const pane = doc.querySelector('#chat-pane');
          if (pane) {
            pane.scrollTo({ top: pane.scrollHeight, behavior: 'smooth' });
          } else {
            const main = doc.querySelector('section.main');
            if (main) main.scrollTo({ top: main.scrollHeight, behavior: 'smooth' });
          }
        </script>
        """,
        height=0,
    )


def new_conversation():
    st.session_state.messages = []
    st.session_state.profile = {}
    st.session_state.used_snippets = []
    st.session_state.phase = "collect"
    st.session_state.last_rendered_count = 0
    st.session_state.language_hint = None
    st.session_state.greeted = False


# ===== Header (title centered, "new chat" button on the left) =====
header_left, header_center, header_right = st.columns([1, 3, 1])

with header_left:
    st.markdown("<div style='padding-top:40px;'></div>",
                unsafe_allow_html=True)  # push down
    if st.button("🆕 שיחה חדשה", key="new_chat"):
        new_conversation()
        st.rerun()

with header_center:
    st.markdown(
        "<h1 style='text-align: center; margin: 12px 0;'>💬 עוזר שירותים רפואיים</h1>",
        unsafe_allow_html=True
    )

with header_right:
    st.write("")



# ===== Initial friendly greeting (once per new chat) =====
if not st.session_state.greeted and not st.session_state.messages:
    st.session_state.messages.append({
        "role": "assistant",
        "content": "שלום! 👋 כדי להתחיל, מה שמך הפרטי ושם המשפחה?"
    })
    st.session_state.greeted = True

# Dedicated chat container so we can render immediately before API responses
chat_holder = st.empty()
render_chat_into(chat_holder)

# ===== Input =====
prompt = st.chat_input("כאן כותבים את ההודעה")

if prompt:
    # 1) Append user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    # 2) Append animated typing placeholder and render immediately
    st.session_state.messages.append({"role": "assistant", "content": TYPING_MARKER})
    render_chat_into(chat_holder)
    auto_scroll_to_bottom()

    # 3) Call the right endpoint based on phase
    phase = "collect" if st.session_state.phase == "collect" else "qa"
    try:
        if phase == "collect":
            payload = {
                "messages": st.session_state.messages[:-1],  # exclude typing marker
                "language_hint": st.session_state.language_hint,
                "user_profile": st.session_state.profile,
            }
            resp = requests.post(f"{API_BASE}/chat/collect_user_info", json=payload, timeout=60)
            if resp.ok:
                data = resp.json()
                reply = data["assistant_message"]
                st.session_state.profile = data.get("updated_profile", {}) or st.session_state.profile
                if data.get("profile_confirmed"):
                    st.session_state.phase = "qa"
            else:
                reply = "מצטער, לא הצלחתי לעבד את ההודעה כרגע."
        else:
            payload = {
                "messages": st.session_state.messages[:-1],  # exclude typing marker
                "user_profile": st.session_state.profile,
                "language_hint": st.session_state.language_hint,
            }
            resp = requests.post(f"{API_BASE}/chat/qa", json=payload, timeout=60)
            if resp.ok:
                data = resp.json()
                reply = data["answer"]
                st.session_state.used_snippets = data.get("used_snippets", [])
            else:
                reply = "לא הצלחתי לענות עכשיו. ננסה שוב עוד רגע."
    except Exception:
        reply = "יש תקלה רגעית בתקשורת. אפשר לשלוח שוב?"

    # 4) Replace typing marker with real reply
    for i in range(len(st.session_state.messages) - 1, -1, -1):
        if (
            st.session_state.messages[i]["role"] == "assistant"
            and st.session_state.messages[i]["content"] == TYPING_MARKER
        ):
            st.session_state.messages[i] = {"role": "assistant", "content": reply}
            break
    else:
        st.session_state.messages.append({"role": "assistant", "content": reply})

    # 5) Re-render updated chat
    render_chat_into(chat_holder)
    auto_scroll_to_bottom()
