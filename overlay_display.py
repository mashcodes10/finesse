#!/usr/bin/env python3
"""
Finesse Overlay Display
─────────────────────────────────────────────────────────────────────
Hold Ctrl+\\ → overlay appears showing the latest quiz answers
Release Ctrl+\\ → overlay disappears

Requires:
  - pyobjc-framework-Quartz  (already in requirements_mac.txt)
  - tkinter                  (Python standard library on macOS)

First run: macOS will ask for Accessibility permission.
  System Preferences → Privacy & Security → Accessibility → add Terminal (or your Python app)

Response file: /tmp/finesse_latest_response.txt
  (written by mac_screenshot_daemon.py polling Oracle Cloud)
"""

import sys
import threading
import tkinter as tk
from pathlib import Path

RESPONSE_FILE = '/tmp/finesse_latest_response.txt'
BACKSLASH_KEYCODE = 42       # macOS virtual keycode for backslash
CTRL_FLAG = 0x40000          # kCGEventFlagMaskControl


class OverlayApp:
    def __init__(self):
        # Hidden root window (tkinter requires one)
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Finesse Overlay Root")

        self._build_overlay()
        self._start_key_listener()

    # ── Overlay window ────────────────────────────────────────────────────────

    def _build_overlay(self):
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.overrideredirect(True)          # No title bar / decorations
        win.attributes('-topmost', True)    # Float above all windows
        win.attributes('-alpha', 0.93)
        win.configure(bg='#0d1117')

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w  = int(sw * 0.52)
        h  = int(sh * 0.52)
        x  = (sw - w) // 2
        y  = int(sh * 0.09)
        win.geometry(f'{w}x{h}+{x}+{y}')

        # ── Header bar ────────────────────────────────────────────────────────
        header = tk.Frame(win, bg='#161b22', pady=8, padx=16)
        header.pack(fill='x')

        tk.Label(
            header,
            text=' Quiz Answers',
            font=('Helvetica Neue', 15, 'bold'),
            fg='#58a6ff',
            bg='#161b22'
        ).pack(side='left')

        tk.Label(
            header,
            text='Hold Ctrl+\\  •  release to hide',
            font=('Helvetica Neue', 11),
            fg='#6e7681',
            bg='#161b22'
        ).pack(side='right')

        # Separator line
        tk.Frame(win, bg='#30363d', height=1).pack(fill='x')

        # ── Text area ─────────────────────────────────────────────────────────
        text_frame = tk.Frame(win, bg='#0d1117')
        text_frame.pack(fill='both', expand=True)

        scrollbar = tk.Scrollbar(text_frame, bg='#30363d', troughcolor='#0d1117',
                                  relief='flat', bd=0)
        scrollbar.pack(side='right', fill='y')

        self.text = tk.Text(
            text_frame,
            font=('Menlo', 14),
            fg='#e6edf3',
            bg='#0d1117',
            wrap='word',
            relief='flat',
            bd=0,
            padx=22,
            pady=18,
            state='disabled',
            yscrollcommand=scrollbar.set,
            selectbackground='#1f6feb',
            insertbackground='white',
            spacing1=2,
            spacing2=2,
            spacing3=4,
        )
        self.text.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.text.yview)

        # Tag for answer highlight (numbers bold)
        self.text.tag_configure('answer_num', foreground='#58a6ff',
                                 font=('Menlo', 14, 'bold'))

        self.win = win

    # ── Show / Hide ───────────────────────────────────────────────────────────

    def _read_response(self) -> str:
        try:
            p = Path(RESPONSE_FILE)
            if p.exists():
                content = p.read_text(encoding='utf-8').strip()
                return content if content else '(Response file is empty)'
            return (
                '(No response yet)\n\n'
                'Waiting for quiz answers from VM...\n'
                f'Expected at: {RESPONSE_FILE}\n\n'
                'Make sure:\n'
                '  1. quiz_answer_watcher.py is running on the VM\n'
                '  2. mac_screenshot_daemon.py is running with response syncing\n'
                '  3. upload_folder = "quiz-screenshots/" in the daemon'
            )
        except Exception as e:
            return f'(Error reading response: {e})'

    def show(self):
        """Called from main thread — refresh content and show window."""
        content = self._read_response()
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', content)
        self.text.configure(state='disabled')
        self.text.yview_moveto(0)   # Scroll to top
        self.win.deiconify()
        self.win.lift()

    def hide(self):
        """Called from main thread — hide window."""
        self.win.withdraw()

    # ── Keyboard listener (background thread) ─────────────────────────────────

    def _start_key_listener(self):
        t = threading.Thread(target=self._key_listener_loop, daemon=True)
        t.start()

    def _key_listener_loop(self):
        try:
            import Quartz
            import CoreFoundation
        except ImportError:
            print("ERROR: pyobjc-framework-Quartz not installed.")
            print("Run: pip install pyobjc-framework-Quartz")
            return

        key_held = [False]

        def callback(proxy, event_type, event, refcon):
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )
            flags = Quartz.CGEventGetFlags(event)
            ctrl  = bool(flags & CTRL_FLAG)

            if event_type == Quartz.kCGEventKeyDown and keycode == BACKSLASH_KEYCODE and ctrl:
                if not key_held[0]:
                    key_held[0] = True
                    # Schedule show() on the main (tkinter) thread
                    self.root.after(0, self.show)

            elif event_type == Quartz.kCGEventKeyUp and keycode == BACKSLASH_KEYCODE:
                if key_held[0]:
                    key_held[0] = False
                    # Schedule hide() on the main (tkinter) thread
                    self.root.after(0, self.hide)

            return event  # Pass event through (don't suppress)

        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown) |
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
        )
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            mask,
            callback,
            None
        )

        if tap is None:
            print()
            print("=" * 60)
            print("ERROR: Could not create keyboard event tap.")
            print()
            print("Fix: Grant Accessibility permission to Terminal (or Python):")
            print("  System Preferences → Privacy & Security → Accessibility")
            print("  Click + and add Terminal.app (or your Python executable)")
            print("=" * 60)
            print()
            return

        source = CoreFoundation.CFMachPortCreateRunLoopSource(None, tap, 0)
        loop   = CoreFoundation.CFRunLoopGetCurrent()
        CoreFoundation.CFRunLoopAddSource(loop, source, CoreFoundation.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)

        print(f"Key listener active — hold Ctrl+\\ to view quiz answers")
        print(f"Response file: {RESPONSE_FILE}")
        CoreFoundation.CFRunLoopRun()

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self):
        print("Finesse Overlay Display started.")
        print(f"Hold Ctrl+\\ to view answers  |  Release to hide")
        print(f"Reading from: {RESPONSE_FILE}")
        self.root.mainloop()


if __name__ == '__main__':
    OverlayApp().run()
