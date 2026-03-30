"""
chat_popup.py — drop-in replacement for show_chat_popup() and its helpers.

Fixes addressed
───────────────
1. Drag-only-from-header  — the title bar is the only draggable zone; the
   message area allows normal text selection / scrolling.
2. Markdown rendering      — mistune 3.x AST → tk.Text tags for bold, italic,
   inline-code, fenced code blocks, headings, and bullet / ordered lists.
3. Scrollable message area — tk.Canvas + Scrollbar; mousewheel works on every
   platform; the canvas auto-resizes its scroll region as new messages arrive.
4. Sensible sizing          — fixed 480 × 560 default; the window is resizable;
   the layout uses grid weights so the message area stretches while the input
   bar stays pinned to the bottom.
"""

import platform
import threading
import tkinter as tk

import mistune  # pip install mistune

from constants import (
    BG, SURFACE, SURFACE1, OVERLAY, MUTED, SUBTEXT, TEXT_C as TEXT,
    BLUE, CYAN, GREEN, YELLOW, RED,
    MAUVE, CODE_BG, CODE_FG, SCROLLBAR, SAPPHIRE,
    FONT_UI, FONT_BOLD, FONT_ITAL, FONT_BI, FONT_MONO,
    FONT_H1, FONT_H2, FONT_H3, FONT_SM, FONT_XS, WRAP_WIDTH,
    bind_hover,
)

# ── Markdown → tk.Text renderer ───────────────────────────────────────────────

def _configure_tags(widget: tk.Text) -> None:
    """Register all rich-text tags on a tk.Text widget."""
    widget.tag_configure("normal",    font=FONT_UI,   foreground=TEXT)
    widget.tag_configure("bold",      font=FONT_BOLD, foreground=TEXT)
    widget.tag_configure("italic",    font=FONT_ITAL, foreground=TEXT)
    widget.tag_configure("boldital",  font=FONT_BI,   foreground=TEXT)
    widget.tag_configure("h1",        font=FONT_H1,   foreground=MAUVE,
                         spacing1=6, spacing3=4)
    widget.tag_configure("h2",        font=FONT_H2,   foreground=MAUVE,
                         spacing1=4, spacing3=2)
    widget.tag_configure("h3",        font=FONT_H3,   foreground=MAUVE,
                         spacing1=2, spacing3=2)
    widget.tag_configure("code",      font=FONT_MONO, foreground=CYAN,
                         background=CODE_BG,
                         selectbackground=OVERLAY)
    widget.tag_configure("codeblock", font=FONT_MONO, foreground=CODE_FG,
                         background=CODE_BG,
                         selectbackground=OVERLAY,
                         lmargin1=10, lmargin2=10, rmargin=10,
                         spacing1=6, spacing3=6)
    widget.tag_configure("bullet",    lmargin1=10, lmargin2=22,
                         font=FONT_UI, foreground=TEXT)
    widget.tag_configure("ol_item",   lmargin1=10, lmargin2=26,
                         font=FONT_UI, foreground=TEXT)
    widget.tag_configure("user_text", font=FONT_UI,   foreground=BLUE)
    widget.tag_configure("ai_label",  font=FONT_BOLD, foreground=MUTED)
    widget.tag_configure("divider",   font=("Segoe UI", 4))


_md_parser = mistune.create_markdown(renderer="ast")


def _insert_inline(widget: tk.Text, nodes: list, extra_tags: tuple = ()) -> None:
    """Recursively insert inline AST nodes into the widget."""
    for node in nodes:
        t = node.get("type")
        raw = node.get("raw", "")
        children = node.get("children") or []

        if t == "text":
            widget.insert(tk.END, raw, ("normal",) + extra_tags)
        elif t == "softbreak":
            widget.insert(tk.END, "\n", ("normal",) + extra_tags)
        elif t == "linebreak":
            widget.insert(tk.END, "\n", ("normal",) + extra_tags)
        elif t == "codespan":
            widget.insert(tk.END, raw, ("code",) + extra_tags)
        elif t == "strong":
            new_tags = _merge_tag("bold", extra_tags)
            _insert_inline(widget, children, new_tags)
        elif t == "emphasis":
            new_tags = _merge_tag("italic", extra_tags)
            _insert_inline(widget, children, new_tags)
        elif t in ("link", "image"):
            # Render link text / alt text only
            _insert_inline(widget, children, extra_tags)
        else:
            # Fallback: recurse into children or print raw
            if children:
                _insert_inline(widget, children, extra_tags)
            elif raw:
                widget.insert(tk.END, raw, ("normal",) + extra_tags)


def _merge_tag(tag: str, existing: tuple) -> tuple:
    """Return a tag tuple that combines bold + italic into 'boldital'."""
    result = set(existing) | {tag}
    if "bold" in result and "italic" in result:
        result -= {"bold", "italic"}
        result.add("boldital")
    return tuple(result)


def _insert_block(widget: tk.Text, node: dict, list_counter: list | None = None) -> None:
    """Insert a single block-level AST node."""
    t = node.get("type")
    children = node.get("children") or []

    if t in ("blank_line",):
        return

    if t == "paragraph":
        _insert_inline(widget, children)
        widget.insert(tk.END, "\n\n", "normal")

    elif t == "block_text":
        # Appears as direct child of list_item in tight lists
        _insert_inline(widget, children)

    elif t == "heading":
        level = node.get("attrs", {}).get("level", 1)
        tag = {1: "h1", 2: "h2", 3: "h3"}.get(level, "h3")
        _insert_inline(widget, children, (tag,))
        widget.insert(tk.END, "\n\n", "normal")

    elif t == "block_code":
        raw_code = node.get("raw", "").rstrip("\n")
        widget.insert(tk.END, raw_code + "\n", "codeblock")
        widget.insert(tk.END, "\n", "normal")

    elif t == "list":
        ordered = node.get("attrs", {}).get("ordered", False)
        counter = [0]
        for item in children:
            _insert_list_item(widget, item, ordered, counter)
        widget.insert(tk.END, "\n", "normal")

    elif t == "block_quote":
        widget.insert(tk.END, "❝ ", ("italic",))
        for child in children:
            _insert_block(widget, child)

    elif t == "thematic_break":
        widget.insert(tk.END, "─" * 48 + "\n\n", "normal")

    else:
        # Generic fallback
        if children:
            for child in children:
                _insert_block(widget, child)
        elif node.get("raw"):
            widget.insert(tk.END, node["raw"] + "\n", "normal")


def _insert_list_item(widget: tk.Text, node: dict, ordered: bool, counter: list) -> None:
    counter[0] += 1
    bullet = f"{counter[0]}. " if ordered else "• "
    tag = "ol_item" if ordered else "bullet"
    widget.insert(tk.END, bullet, (tag,))
    for child in (node.get("children") or []):
        # block_text children render inline on the same line
        if child.get("type") in ("block_text", "paragraph"):
            _insert_inline(widget, child.get("children") or [], (tag,))
        else:
            _insert_block(widget, child)
    widget.insert(tk.END, "\n", tag)


def render_markdown_to_text(widget: tk.Text, markdown_str: str) -> None:
    """Parse *markdown_str* and insert it into *widget* with rich-text tags."""
    ast = _md_parser(markdown_str)
    if not isinstance(ast, list):
        widget.insert(tk.END, markdown_str, "normal")
        return
    for node in ast:
        _insert_block(widget, node)


# ── Right-click copy menu ─────────────────────────────────────────────────────

def _show_copy_menu(widget: tk.Text, event) -> str:
    """Show a minimal right-click context menu with Copy / Select All."""
    menu = tk.Menu(widget, tearoff=0,
                   bg=SURFACE, fg=TEXT, activebackground=OVERLAY,
                   activeforeground=TEXT, relief="flat", bd=0,
                   font=("Segoe UI", 9))

    def _copy():
        try:
            sel = widget.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            sel = widget.get("1.0", tk.END).strip()
        if sel:
            widget.clipboard_clear()
            widget.clipboard_append(sel)

    def _select_all():
        widget.tag_add(tk.SEL, "1.0", tk.END)
        widget.mark_set(tk.INSERT, "1.0")
        widget.see(tk.INSERT)

    menu.add_command(label="Copy",       command=_copy)
    menu.add_command(label="Select all", command=_select_all)
    menu.tk_popup(event.x_root, event.y_root)
    return "break"


# ── Scrollable message frame ──────────────────────────────────────────────────

class ScrollableMessageFrame(tk.Frame):
    """
    A vertically-scrollable area that holds per-message tk.Text widgets.

    Why tk.Text per message instead of one big Text widget?
    ────────────────────────────────────────────────────────
    Each message needs its own background (user vs AI), and we want the
    "user" bubble to be right-aligned while the AI bubble is left-aligned.
    One monolithic Text widget makes that very hard.  A separate Text per
    message inside a scrolled canvas gives us both per-bubble styling AND
    the full tag-based Markdown renderer.
    """

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)

        self._canvas = tk.Canvas(self, bg=BG, highlightthickness=0,
                                 bd=0, relief="flat")
        self._scrollbar = tk.Scrollbar(self, orient="vertical",
                                       command=self._canvas.yview,
                                       bg=SURFACE, troughcolor=BG,
                                       activebackground=OVERLAY,
                                       highlightthickness=0, bd=0,
                                       relief="flat", width=6)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left",  fill="both", expand=True)

        # Inner frame that holds the message widgets
        self._inner = tk.Frame(self._canvas, bg=BG)
        self._window_id = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw"
        )

        self._inner.bind("<Configure>", self._on_inner_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._bind_mousewheel(self._canvas)
        self._bind_mousewheel(self._inner)

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _on_inner_resize(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        # Make the inner frame fill the canvas width
        self._canvas.itemconfig(self._window_id, width=event.width)

    def _bind_mousewheel(self, widget):
        widget.bind("<MouseWheel>",       self._on_mousewheel, add=True)
        widget.bind("<Button-4>",         self._on_mousewheel, add=True)  # Linux
        widget.bind("<Button-5>",         self._on_mousewheel, add=True)  # Linux

    def _on_mousewheel(self, event):
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll( 1, "units")
        else:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def scroll_to_bottom(self):
        self._canvas.update_idletasks()
        self._canvas.yview_moveto(1.0)

    # ── Public API ────────────────────────────────────────────────────────────

    def add_message(self, role: str, text: str) -> None:
        """Append a new message bubble (user or AI) to the frame."""
        is_user = role == "user"
        pad_x   = 10

        outer = tk.Frame(self._inner, bg=BG)
        outer.pack(fill="x", padx=pad_x, pady=(4, 0),
                   anchor="e" if is_user else "w")

        label_text = "You" if is_user else "AI"
        label_fg   = BLUE if is_user else MUTED
        tk.Label(outer, text=label_text, bg=BG, fg=label_fg,
                 font=("Segoe UI", 8, "bold")).pack(
                     anchor="e" if is_user else "w")

        bubble_bg = SURFACE if is_user else BG
        bubble_bd = 1

        # We use a tk.Text so we can apply Markdown tags.
        # height=1 is a starting guess; we'll auto-fit below.
        msg_text = tk.Text(
            outer,
            bg=bubble_bg, fg=TEXT,
            font=FONT_UI,
            relief="flat",
            bd=bubble_bd,
            padx=10, pady=8,
            wrap="word",
            cursor="xterm",        # I-beam: signals text is selectable
            state="normal",
            highlightthickness=0,
            selectbackground=OVERLAY,
            selectforeground=TEXT,
            inactiveselectbackground=OVERLAY,  # keep highlight when focus leaves
            spacing1=2, spacing3=2,
            width=52,              # characters; controls natural wrap width
        )
        _configure_tags(msg_text)

        if is_user:
            msg_text.insert(tk.END, text, "user_text")
        else:
            render_markdown_to_text(msg_text, text)

        # Strip trailing blank lines the renderer may have added
        content = msg_text.get("1.0", tk.END)
        stripped = content.rstrip("\n")
        if len(stripped) < len(content) - 1:
            msg_text.delete(f"1.0 + {len(stripped)}c", tk.END)

        # Keep the widget visually read-only: block every keystroke that would
        # insert or delete content, but let selection shortcuts through.
        # Using state="disabled" would block selection entirely, so we stay
        # in state="normal" and intercept keys instead.
        def _block_edits(event):
            # Allow copy / select-all / cursor movement / scrolling
            if event.state & 0x4:          # Ctrl held
                if event.keysym.lower() in ("a", "c"):
                    return                 # let Tk handle these natively
                return "break"             # block all other Ctrl combos
            # Allow navigation and selection keys
            if event.keysym in (
                "Left", "Right", "Up", "Down",
                "Home", "End", "Prior", "Next",   # Page Up / Down
                "Shift_L", "Shift_R",
                "Control_L", "Control_R",
            ):
                return
            # Block everything else (printable chars, Delete, BackSpace…)
            return "break"

        msg_text.bind("<Key>", _block_edits)
        # Also block right-click paste via the default Tk context menu
        msg_text.bind("<Button-3>", lambda e: _show_copy_menu(msg_text, e))

        msg_text.config(state="normal")   # stays normal so selection works

        # Auto-fit height: count display lines
        msg_text.update_idletasks()
        line_count = int(msg_text.index(tk.END).split(".")[0])
        msg_text.config(height=max(1, line_count))

        # Re-bind mousewheel so scrolling still works inside the bubble
        self._bind_mousewheel(msg_text)

        msg_text.pack(fill="x", anchor="e" if is_user else "w")

        # Small spacer
        tk.Frame(self._inner, bg=BG, height=4).pack(fill="x")

        self.scroll_to_bottom()


# ── Focus helper ──────────────────────────────────────────────────────────────

def _force_focus(popup: tk.Toplevel, entry: tk.Entry | None = None):
    try:
        if not popup.winfo_exists():
            return
        popup.lift()
        popup.focus_force()
        if entry:
            entry.focus_force()
            entry.icursor(tk.END)
        if platform.system() == "Windows":
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(popup.winfo_id())
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


# ── Shared close-outside binding ─────────────────────────────────────────────

def _bind_close_outside(popup: tk.Toplevel, close_fn):
    """Close popup when clicking outside it. Cleans up on destroy."""
    def on_click_outside(e=None):
        try:
            if not popup.winfo_exists():
                _unbind()
                return
            px, py = popup.winfo_rootx(), popup.winfo_rooty()
            pw, ph = popup.winfo_width(), popup.winfo_height()
            mx, my = popup.winfo_pointerx(), popup.winfo_pointery()
            if not (px <= mx <= px + pw and py <= my <= py + ph):
                _unbind()
                close_fn()
        except Exception:
            pass
    popup.bind_all("<Button-1>", on_click_outside, add=True)
    def _unbind():
        try:
            popup.unbind_all("<Button-1>")
        except Exception:
            pass
    popup.bind("<Destroy>", lambda e: _unbind(), add=True)


# ── Chat popup (main entry point) ─────────────────────────────────────────────

def show_chat_popup(
    selected_text: str,
    get_tk_root,          # callable → tk.Tk hidden root
    chat_with_context,    # callable(text, question, history) → str
    get_config,           # callable() → dict snapshot
) -> None:
    """
    Open the chat popup as a Toplevel child of the hidden root.

    Parameters
    ──────────
    selected_text     : the text the user had selected when they pressed the hotkey
    get_tk_root       : factory for the shared hidden tk.Tk root
    chat_with_context : function that calls the OpenAI API
    get_config        : function that returns a config snapshot dict
    """
    root = get_tk_root()
    popup = tk.Toplevel(root)
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.attributes("-alpha", 0.97)
    popup.configure(bg=BG)

    # ── Window size & minimum ─────────────────────────────────────────────────
    WIN_W, WIN_H = 480, 560
    MIN_W, MIN_H = 360, 300
    popup.minsize(MIN_W, MIN_H)
    popup.resizable(True, True)

    # Position near cursor
    popup.update_idletasks()
    cx = popup.winfo_pointerx() + 16
    cy = popup.winfo_pointery() + 16
    sw = popup.winfo_screenwidth()
    sh = popup.winfo_screenheight()
    if cx + WIN_W > sw: cx = sw - WIN_W - 10
    if cy + WIN_H > sh: cy = sh - WIN_H - 10
    popup.geometry(f"{WIN_W}x{WIN_H}+{cx}+{cy}")

    chat_history: list[dict] = []

    def close(e=None):
        try:
            popup.destroy()
        except Exception:
            pass

    # ── Root grid: header / context / messages / input ────────────────────────
    popup.grid_rowconfigure(0, weight=0)   # header
    popup.grid_rowconfigure(1, weight=0)   # context strip
    popup.grid_rowconfigure(2, weight=1)   # messages (expands)
    popup.grid_rowconfigure(3, weight=0)   # input bar
    popup.grid_columnconfigure(0, weight=1)

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 0 — Header / title bar  (THE ONLY DRAGGABLE ZONE)
    # ─────────────────────────────────────────────────────────────────────────
    header = tk.Frame(popup, bg=SURFACE, height=36)
    header.grid(row=0, column=0, sticky="ew")
    header.grid_propagate(False)
    header.grid_columnconfigure(0, weight=1)

    tk.Label(header, text="💬  Chat", bg=SURFACE, fg=TEXT,
             font=("Segoe UI", 9, "bold"), padx=12).grid(
                 row=0, column=0, sticky="w", pady=8)

    close_btn = tk.Button(header, text="✕", command=close,
              bg=SURFACE, fg=MUTED, font=FONT_SM,
              relief="flat", padx=8, pady=0, bd=0,
              cursor="hand2", activebackground=RED,
              activeforeground=TEXT)
    close_btn.grid(row=0, column=1, sticky="e", padx=4)
    bind_hover(close_btn, RED, SURFACE, TEXT, MUTED)

    # Drag state — attached only to the header
    _drag = {"x": 0, "y": 0, "active": False}

    def _header_press(event):
        _drag["x"] = event.x_root - popup.winfo_x()
        _drag["y"] = event.y_root - popup.winfo_y()
        _drag["active"] = True

    def _header_drag(event):
        if not _drag["active"]:
            return
        popup.geometry(f"+{event.x_root - _drag['x']}+{event.y_root - _drag['y']}")

    def _header_release(_event):
        _drag["active"] = False

    for widget in (header, header.winfo_children()[0]):
        widget.bind("<Button-1>",   _header_press,   add=True)
        widget.bind("<B1-Motion>",  _header_drag,    add=True)
        widget.bind("<ButtonRelease-1>", _header_release, add=True)

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 1 — Context strip (selected text preview)
    # ─────────────────────────────────────────────────────────────────────────
    ctx_frame = tk.Frame(popup, bg=BG)
    ctx_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 0))

    orig_short = selected_text if len(selected_text) < 90 else selected_text[:87] + "…"
    tk.Label(ctx_frame, text=orig_short, bg=BG, fg=MUTED,
             font=("Segoe UI", 8), wraplength=440, justify="left",
             anchor="w").pack(fill="x")

    tk.Frame(popup, bg=SURFACE, height=1).grid(
        row=1, column=0, sticky="ew", padx=12, pady=(6, 0))

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 2 — Scrollable message area
    # ─────────────────────────────────────────────────────────────────────────
    msg_area = ScrollableMessageFrame(popup)
    msg_area.grid(row=2, column=0, sticky="nsew", padx=0, pady=(4, 0))

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 3 — Input bar
    # ─────────────────────────────────────────────────────────────────────────
    input_frame = tk.Frame(popup, bg=SURFACE)
    input_frame.grid(row=3, column=0, sticky="ew")
    input_frame.grid_columnconfigure(0, weight=1)

    tk.Frame(input_frame, bg=OVERLAY, height=1).grid(
        row=0, column=0, columnspan=2, sticky="ew")

    input_var = tk.StringVar()
    input_entry = tk.Entry(
        input_frame, textvariable=input_var,
        bg=SURFACE, fg=TEXT, insertbackground=TEXT,
        font=FONT_UI, relief="flat",
        highlightthickness=0, bd=0,
    )
    input_entry.grid(row=1, column=0, sticky="ew",
                     padx=(12, 6), pady=10, ipady=6)

    send_btn = tk.Button(
        input_frame, text="Send ⏎",
        bg=BLUE, fg=BG, font=("Segoe UI", 9, "bold"),
        relief="flat", padx=12, pady=6, cursor="hand2",
        activebackground=SAPPHIRE, activeforeground=BG, bd=0,
    )
    send_btn.grid(row=1, column=1, sticky="e", padx=(0, 12), pady=10)
    bind_hover(send_btn, SAPPHIRE, BLUE)

    # ── Resize grip (bottom-right corner) ────────────────────────────────────
    grip = tk.Label(popup, text="⠿", bg=BG, fg=MUTED,
                    font=("Segoe UI", 10), cursor="sizing")
    grip.place(relx=1.0, rely=1.0, anchor="se", x=-2, y=-2)

    _resize = {"x": 0, "y": 0, "w": WIN_W, "h": WIN_H}

    def _grip_press(event):
        _resize["x"] = event.x_root
        _resize["y"] = event.y_root
        _resize["w"] = popup.winfo_width()
        _resize["h"] = popup.winfo_height()

    def _grip_drag(event):
        dw = event.x_root - _resize["x"]
        dh = event.y_root - _resize["y"]
        nw = max(MIN_W, _resize["w"] + dw)
        nh = max(MIN_H, _resize["h"] + dh)
        popup.geometry(f"{nw}x{nh}")

    grip.bind("<Button-1>",  _grip_press)
    grip.bind("<B1-Motion>", _grip_drag)

    # ── Send logic ────────────────────────────────────────────────────────────
    def send(e=None):
        question = input_var.get().strip()
        if not question:
            return
        input_var.set("")
        send_btn.config(state="disabled", text="⏳", bg=MUTED)
        msg_area.add_message("user", question)

        def do_chat():
            reply = chat_with_context(selected_text, question, chat_history)
            chat_history.append({"role": "user",      "content": question})
            chat_history.append({"role": "assistant", "content": reply})
            if popup.winfo_exists():
                popup.after(0, lambda: msg_area.add_message("assistant", reply))
                popup.after(0, lambda: send_btn.config(
                    state="normal", text="Send ⏎", bg=BLUE))

        threading.Thread(target=do_chat, daemon=True).start()

    send_btn.config(command=send)
    input_entry.bind("<Return>", send)
    popup.bind("<Escape>", close)
    _bind_close_outside(popup, close)

    # Focus the entry after the window is fully drawn
    popup.after(100, lambda: _force_focus(popup, input_entry))
    popup.after(300, lambda: _force_focus(popup, input_entry))


# ── Integration shim ──────────────────────────────────────────────────────────
# If you are dropping this file alongside the existing main.py, replace the
# original show_chat_popup with this thin wrapper that imports from here:
#
#   from chat_popup import show_chat_popup as _chat_popup
#
#   def show_chat_popup(selected_text: str) -> None:
#       _chat_popup(
#           selected_text,
#           get_tk_root=get_tk_root,
#           chat_with_context=chat_with_context,
#           get_config=get_config,
#       )