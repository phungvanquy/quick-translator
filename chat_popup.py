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
    BG, SURFACE, SURFACE1, SURFACE2, OVERLAY, MUTED, SUBTEXT, TEXT_C as TEXT,
    BLUE, CYAN, GREEN, YELLOW, RED,
    MAUVE, CODE_BG, CODE_FG, SCROLLBAR, SAPPHIRE,
    BORDER, SHADOW, USER_BG, AI_BG, INPUT_BG, INPUT_BORDER, ACCENT,
    BTN_PRIMARY_BG, BTN_PRIMARY_FG, BTN_PRIMARY_HOVER,
    FONT_UI, FONT_BOLD, FONT_ITAL, FONT_BI, FONT_MONO, FONT_BTN,
    FONT_H1, FONT_H2, FONT_H3, FONT_SM, FONT_XS, WRAP_WIDTH,
    PAD_SM, PAD, PAD_LG,
    bind_hover, fade_in, LoadingSpinner,
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
    # Destroy the menu after it's dismissed to avoid accumulating widgets
    menu.bind("<Unmap>", lambda e: widget.after_idle(menu.destroy))
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
                                       bg=SURFACE1, troughcolor=BG,
                                       activebackground=SURFACE2,
                                       highlightthickness=0, bd=0,
                                       relief="flat", width=5)
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
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._canvas.yview_moveto(1.0)

    # ── Public API ────────────────────────────────────────────────────────────

    def add_message(self, role: str, text: str) -> None:
        """Append a new message bubble (user or AI) to the frame."""
        is_user = role == "user"
        pad_x   = PAD

        outer = tk.Frame(self._inner, bg=BG)
        outer.pack(fill="x", padx=pad_x, pady=(PAD_SM, 0),
                   anchor="e" if is_user else "w")

        label_text = "You" if is_user else "AI"
        label_fg   = ACCENT if is_user else MUTED
        tk.Label(outer, text=label_text, bg=BG, fg=label_fg,
                 font=("Segoe UI", 8, "bold")).pack(
                     anchor="e" if is_user else "w", pady=(0, 2))

        bubble_bg = USER_BG if is_user else AI_BG

        msg_text = tk.Text(
            outer,
            bg=bubble_bg, fg=TEXT,
            font=FONT_UI,
            relief="flat",
            bd=0,
            padx=PAD, pady=10,
            wrap="word",
            cursor="xterm",        # I-beam: signals text is selectable
            state="normal",
            highlightthickness=0,
            selectbackground=OVERLAY,
            selectforeground=TEXT,
            inactiveselectbackground=OVERLAY,  # keep highlight when focus leaves
            spacing1=2, spacing3=2,
            width=52,              # characters; controls natural wrap width
            height=1,              # start small; auto-fit below
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

        # Re-bind mousewheel so scrolling still works inside the bubble
        self._bind_mousewheel(msg_text)

        # Pack first so word-wrap can be calculated against actual width
        msg_text.pack(fill="x", anchor="e" if is_user else "w")
        msg_text.update_idletasks()

        # Auto-fit height using display lines (accounts for word wrap)
        try:
            dl = msg_text.count("1.0", tk.END, "displaylines")
            display_lines = int(dl[0]) if dl else 1
        except (TypeError, IndexError, tk.TclError):
            display_lines = max(1, int(msg_text.index(tk.END).split(".")[0]) - 1)
        msg_text.config(height=max(1, display_lines))

        # Small spacer
        tk.Frame(self._inner, bg=BG, height=4).pack(fill="x")

        self.scroll_to_bottom()

    def start_streaming_message(self) -> dict:
        """Create an empty AI bubble and return a handle for streaming.

        Returns a dict with:
          - 'widget': the tk.Text widget to append to
          - 'outer': the outer frame
          - 'append': callable(chunk_str) to append text
          - 'finish': callable(full_markdown_str) to re-render with markdown
        """
        pad_x = PAD
        outer = tk.Frame(self._inner, bg=BG)
        outer.pack(fill="x", padx=pad_x, pady=(PAD_SM, 0), anchor="w")

        tk.Label(outer, text="AI", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 2))

        msg_text = tk.Text(
            outer, bg=AI_BG, fg=TEXT, font=FONT_UI,
            relief="flat", bd=0, padx=PAD, pady=10,
            wrap="word", cursor="xterm", state="normal",
            highlightthickness=0,
            selectbackground=OVERLAY, selectforeground=TEXT,
            inactiveselectbackground=OVERLAY,
            spacing1=2, spacing3=2, width=52,
            height=1,
        )
        _configure_tags(msg_text)

        # Animated loading spinner instead of static emoji
        _spinner = LoadingSpinner(msg_text)
        _spinner.start()

        def _block_edits(event):
            if event.state & 0x4:
                if event.keysym.lower() in ("a", "c"):
                    return
                return "break"
            if event.keysym in (
                "Left", "Right", "Up", "Down",
                "Home", "End", "Prior", "Next",
                "Shift_L", "Shift_R", "Control_L", "Control_R",
            ):
                return
            return "break"

        msg_text.bind("<Key>", _block_edits)
        msg_text.bind("<Button-3>", lambda e: _show_copy_menu(msg_text, e))
        self._bind_mousewheel(msg_text)
        msg_text.pack(fill="x", anchor="w")

        tk.Frame(self._inner, bg=BG, height=4).pack(fill="x")
        self.scroll_to_bottom()

        _started = {"v": False}
        smf = self

        def _refit():
            try:
                msg_text.update_idletasks()
                dl = msg_text.count("1.0", tk.END, "displaylines")
                display_lines = int(dl[0]) if dl else 1
            except (TypeError, IndexError, tk.TclError):
                display_lines = max(1, int(msg_text.index(tk.END).split(".")[0]) - 1)
            msg_text.config(height=max(1, display_lines))
            smf.scroll_to_bottom()

        def append(chunk: str):
            if not _started["v"]:
                _spinner.stop()
                msg_text.delete("1.0", tk.END)
                _started["v"] = True
            msg_text.insert(tk.END, chunk, "normal")
            _refit()

        def finish(full_md: str):
            _spinner.stop()
            msg_text.delete("1.0", tk.END)
            render_markdown_to_text(msg_text, full_md)
            content = msg_text.get("1.0", tk.END)
            stripped = content.rstrip("\n")
            if len(stripped) < len(content) - 1:
                msg_text.delete(f"1.0 + {len(stripped)}c", tk.END)
            _refit()

        return {"widget": msg_text, "outer": outer, "append": append, "finish": finish}


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
    _state = {"unbound": False}

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

    bind_id = popup.bind_all("<Button-1>", on_click_outside, add=True)

    def _unbind():
        if _state["unbound"]:
            return
        _state["unbound"] = True
        try:
            popup.unbind_all_by_id("<Button-1>", bind_id)
        except (AttributeError, Exception):
            try:
                popup.unbind_all("<Button-1>")
            except Exception:
                pass

    popup.bind("<Destroy>", lambda e: _unbind(), add=True)


# ── Chat popup (main entry point) ─────────────────────────────────────────────

def show_chat_popup(
    selected_text: str,
    get_tk_root,                # callable → tk.Tk hidden root
    chat_with_context_stream,   # callable(text, question, history) → generator of str chunks
    get_config,                 # callable() → dict snapshot
) -> None:
    """
    Open the chat popup as a Toplevel child of the hidden root.

    Parameters
    ──────────
    selected_text            : the text the user had selected when they pressed the hotkey
    get_tk_root              : factory for the shared hidden tk.Tk root
    chat_with_context_stream : streaming generator function that calls the OpenAI API
    get_config               : function that returns a config snapshot dict
    """
    root = get_tk_root()
    popup = tk.Toplevel(root)
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.configure(bg=SHADOW)  # dark 1px shadow border

    # ── Window size & minimum ─────────────────────────────────────────────────
    WIN_W, WIN_H = 500, 580
    MIN_W, MIN_H = 380, 320
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
    fade_in(popup, duration_ms=120)

    chat_history: list[dict] = []
    _ctx = {"text": selected_text}  # mutable context; cleared = free chat

    def close(e=None):
        try:
            popup.destroy()
        except Exception:
            pass

    # ── Root grid: border + content ─────────────────────────────────────────
    # Outer border via a wrapper frame
    border_frame = tk.Frame(popup, bg=BORDER, bd=0)
    border_frame.pack(fill="both", expand=True, padx=1, pady=1)

    content = tk.Frame(border_frame, bg=BG, bd=0)
    content.pack(fill="both", expand=True, padx=1, pady=1)

    content.grid_rowconfigure(0, weight=0)   # header
    content.grid_rowconfigure(1, weight=0)   # context strip
    content.grid_rowconfigure(2, weight=1)   # messages (expands)
    content.grid_rowconfigure(3, weight=0)   # input bar
    content.grid_columnconfigure(0, weight=1)

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 0 — Header / title bar  (THE ONLY DRAGGABLE ZONE)
    # ─────────────────────────────────────────────────────────────────────────
    header = tk.Frame(content, bg=SURFACE, height=40)
    header.grid(row=0, column=0, sticky="ew")
    header.grid_propagate(False)
    header.grid_columnconfigure(0, weight=1)

    header_label = tk.Label(header, text="💬  Chat", bg=SURFACE, fg=TEXT,
             font=("Segoe UI", 10, "bold"), padx=PAD)
    header_label.grid(row=0, column=0, sticky="w", pady=10)

    close_btn = tk.Button(header, text="✕", command=close,
              bg=SURFACE, fg=MUTED, font=FONT_SM,
              relief="flat", padx=10, pady=2, bd=0,
              cursor="hand2", activebackground=RED,
              activeforeground=TEXT)
    close_btn.grid(row=0, column=1, sticky="e", padx=PAD_SM)
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
    # ROW 1 — Context strip (selected text preview, clearable)
    # ─────────────────────────────────────────────────────────────────────────
    ctx_frame = tk.Frame(content, bg=BG)
    ctx_frame.grid(row=1, column=0, sticky="ew", padx=PAD, pady=(10, 0))
    ctx_frame.grid_columnconfigure(0, weight=1)

    orig_short = selected_text if len(selected_text) < 90 else selected_text[:87] + "…"
    ctx_label = tk.Label(ctx_frame, text=orig_short, bg=BG, fg=MUTED,
             font=("Segoe UI", 8), wraplength=420, justify="left",
             anchor="w")
    ctx_label.grid(row=0, column=0, sticky="ew")

    def clear_context():
        _ctx["text"] = ""
        chat_history.clear()
        ctx_frame.grid_forget()
        ctx_sep.grid_forget()
        header_label.config(text="💬  Free Chat")

    clear_ctx_btn = tk.Button(ctx_frame, text="✕", command=clear_context,
                              bg=BG, fg=MUTED, font=FONT_XS,
                              relief="flat", padx=4, pady=0, bd=0,
                              cursor="hand2", activebackground=BG,
                              activeforeground=RED)
    clear_ctx_btn.grid(row=0, column=1, sticky="ne", padx=(4, 0))
    bind_hover(clear_ctx_btn, BG, BG, RED, MUTED)

    ctx_sep = tk.Frame(content, bg=SURFACE1, height=1)
    ctx_sep.grid(row=1, column=0, sticky="ew", padx=PAD, pady=(PAD_SM, 0))

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 2 — Scrollable message area
    # ─────────────────────────────────────────────────────────────────────────
    msg_area = ScrollableMessageFrame(content)
    msg_area.grid(row=2, column=0, sticky="nsew", padx=0, pady=(4, 0))

    # ─────────────────────────────────────────────────────────────────────────
    # ROW 3 — Input bar
    # ─────────────────────────────────────────────────────────────────────────
    input_frame = tk.Frame(content, bg=SURFACE)
    input_frame.grid(row=3, column=0, sticky="ew")
    input_frame.grid_columnconfigure(0, weight=1)

    tk.Frame(input_frame, bg=SURFACE1, height=1).grid(
        row=0, column=0, columnspan=2, sticky="ew")

    input_var = tk.StringVar()
    input_entry = tk.Entry(
        input_frame, textvariable=input_var,
        bg=INPUT_BG, fg=TEXT, insertbackground=TEXT,
        font=FONT_UI, relief="flat",
        highlightthickness=1, highlightbackground=INPUT_BORDER,
        highlightcolor=ACCENT, bd=4,
    )
    input_entry.grid(row=1, column=0, sticky="ew",
                     padx=(PAD, PAD_SM), pady=PAD, ipady=6)

    send_btn = tk.Button(
        input_frame, text="Send",
        bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG, font=FONT_BTN,
        relief="flat", padx=16, pady=7, cursor="hand2",
        activebackground=BTN_PRIMARY_HOVER, activeforeground=BTN_PRIMARY_FG,
        bd=0,
    )
    send_btn.grid(row=1, column=1, sticky="e", padx=(0, PAD), pady=PAD)
    bind_hover(send_btn, BTN_PRIMARY_HOVER, BTN_PRIMARY_BG)

    # ── Resize grip (bottom-right corner) ────────────────────────────────────
    grip = tk.Label(content, text="⠿", bg=BG, fg=MUTED,
                    font=("Segoe UI", 10), cursor="sizing")
    grip.place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-4)

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
        send_btn.config(state="disabled", text="\u2026", bg=MUTED)
        msg_area.add_message("user", question)
        handle = msg_area.start_streaming_message()

        def do_chat():
            full_reply = []
            stream = chat_with_context_stream(_ctx["text"], question, chat_history)
            try:
                for chunk in stream:
                    if not popup.winfo_exists():
                        return
                    full_reply.append(chunk)
                    popup.after(0, lambda c=chunk: handle["append"](c))
            finally:
                # Close the generator to release the HTTP stream
                try:
                    stream.close()
                except Exception:
                    pass
                reply = "".join(full_reply).strip()
                chat_history.append({"role": "user",      "content": question})
                chat_history.append({"role": "assistant", "content": reply})
                # Cap history to last 50 messages to prevent unbounded memory growth
                if len(chat_history) > 50:
                    del chat_history[:len(chat_history) - 50]
                if popup.winfo_exists():
                    popup.after(0, lambda: handle["finish"](reply))
                    popup.after(0, lambda: send_btn.config(
                        state="normal", text="Send", bg=BTN_PRIMARY_BG))

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