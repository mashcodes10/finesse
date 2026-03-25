#!/usr/bin/env python3
"""
Finesse Overlay Display
─────────────────────────────────────────────────────────────────────
Hold Option+. → overlay appears showing the latest quiz answers
Release Option+. → overlay disappears

Requires:
  - pyobjc-framework-Cocoa   (in requirements_mac.txt)
  - pyobjc-framework-Quartz  (in requirements_mac.txt)

First run: macOS will ask for Accessibility permission.
  System Settings → Privacy & Security → Accessibility → add Terminal

Response file: /tmp/finesse_latest_response.txt
"""

import signal
import threading
from pathlib import Path

signal.signal(signal.SIGQUIT, signal.SIG_IGN)

RESPONSE_FILE = '/tmp/finesse_latest_response.txt'
PERIOD_KEYCODE = 47       # macOS virtual keycode for period (.)
OPTION_FLAG    = 0x80000  # kCGEventFlagMaskAlternate

import AppKit
import objc
from Foundation import NSObject, NSMakeRect, NSAttributedString

# Integer constants (avoids version-specific AppKit symbol lookups)
NSWindowStyleMaskBorderless          = 0
NSWindowStyleMaskNonactivatingPanel  = 1 << 7   # 128
NSBackingStoreBuffered               = 2
NSFloatingWindowLevel                = 3
NSViewWidthSizable                   = 2
NSViewHeightSizable                  = 16
NSNoBorder                           = 0
NSApplicationActivationPolicyAccessory = 1

NSWindowCollectionBehaviorCanJoinAllSpaces    = 1 << 0
NSWindowCollectionBehaviorStationary         = 1 << 4
NSWindowCollectionBehaviorFullScreenAuxiliary = 1 << 8

FULLSCREEN_BEHAVIOR = (
    NSWindowCollectionBehaviorCanJoinAllSpaces    |
    NSWindowCollectionBehaviorStationary         |
    NSWindowCollectionBehaviorFullScreenAuxiliary
)


# ── Overlay panel ──────────────────────────────────────────────────────────────

class OverlayPanel(NSObject):

    def init(self):
        self = objc.super(OverlayPanel, self).init()
        if self is None:
            return None
        self._build()
        return self

    def _build(self):
        screen = AppKit.NSScreen.mainScreen()
        sf = screen.frame()
        sw, sh = sf.size.width, sf.size.height

        w = sw * 0.52
        h = sh * 0.52
        x = (sw - w) / 2
        y = sh * 0.09

        self._panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, w, h),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        self._panel.setCollectionBehavior_(FULLSCREEN_BEHAVIOR)
        self._panel.setLevel_(NSFloatingWindowLevel)
        self._panel.setOpaque_(False)
        self._panel.setAlphaValue_(0.75)
        self._panel.setBackgroundColor_(
            AppKit.NSColor.colorWithRed_green_blue_alpha_(0.051, 0.067, 0.090, 1.0)
        )
        self._panel.setHasShadow_(True)

        content = self._panel.contentView()
        bounds  = content.bounds()

        scroll = AppKit.NSScrollView.alloc().initWithFrame_(bounds)
        scroll.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(NSNoBorder)
        scroll.setDrawsBackground_(False)

        tv = AppKit.NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, bounds.size.width, bounds.size.height)
        )
        tv.setEditable_(False)
        tv.setSelectable_(True)
        tv.setDrawsBackground_(True)
        tv.setBackgroundColor_(
            AppKit.NSColor.colorWithRed_green_blue_alpha_(0.051, 0.067, 0.090, 1.0)
        )
        tv.setFont_(AppKit.NSFont.fontWithName_size_('Menlo', 14))
        tv.setTextColor_(
            AppKit.NSColor.colorWithRed_green_blue_alpha_(0.902, 0.929, 0.953, 1.0)
        )
        tv.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        tv.textContainer().setLineFragmentPadding_(22)

        scroll.setDocumentView_(tv)
        content.addSubview_(scroll)

        self._tv = tv

    def show(self):
        self._tv.setString_(self._read_response())
        self._tv.scrollToBeginningOfDocument_(None)
        self._panel.orderFrontRegardless()

    def hide(self):
        self._panel.orderOut_(None)

    def _read_response(self):
        try:
            p = Path(RESPONSE_FILE)
            if p.exists():
                text = p.read_text(encoding='utf-8').strip()
                return text if text else '(Response file is empty)'
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


# ── Key listener ───────────────────────────────────────────────────────────────

class KeyListener(NSObject):

    def initWithOverlay_(self, overlay):
        self = objc.super(KeyListener, self).init()
        if self is None:
            return None
        self._overlay = overlay
        return self

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        try:
            import Quartz
            import CoreFoundation
        except ImportError:
            print("ERROR: pyobjc-framework-Quartz not installed.")
            return

        held    = [False]
        overlay = self._overlay

        def callback(proxy, event_type, event, refcon):
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )
            flags  = Quartz.CGEventGetFlags(event)
            option = bool(flags & OPTION_FLAG)

            if event_type == Quartz.kCGEventKeyDown and keycode == PERIOD_KEYCODE and option:
                if not held[0]:
                    held[0] = True
                    overlay.performSelectorOnMainThread_withObject_waitUntilDone_(
                        'show', None, False
                    )
            elif event_type == Quartz.kCGEventKeyUp and keycode == PERIOD_KEYCODE:
                if held[0]:
                    held[0] = False
                    overlay.performSelectorOnMainThread_withObject_waitUntilDone_(
                        'hide', None, False
                    )
            return event

        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown) |
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
        )
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGHIDEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            mask,
            callback,
            None,
        )
        if tap is None:
            print()
            print("=" * 60)
            print("ERROR: Could not create keyboard event tap.")
            print("Fix: System Settings → Privacy & Security → Accessibility")
            print("=" * 60)
            print()
            return

        source = CoreFoundation.CFMachPortCreateRunLoopSource(None, tap, 0)
        loop   = CoreFoundation.CFRunLoopGetCurrent()
        CoreFoundation.CFRunLoopAddSource(loop, source, CoreFoundation.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)
        print("Key listener active — hold Option+. to view answers")
        CoreFoundation.CFRunLoopRun()


# ── App delegate ───────────────────────────────────────────────────────────────

class AppDelegate(NSObject):

    def applicationDidFinishLaunching_(self, _notification):
        self._overlay  = OverlayPanel.alloc().init()
        self._listener = KeyListener.alloc().initWithOverlay_(self._overlay)
        self._listener.start()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)

    print("Finesse Overlay Display started.")
    print("Hold Option+. to view answers  |  Release to hide")
    print(f"Reading from: {RESPONSE_FILE}")

    app.run()
