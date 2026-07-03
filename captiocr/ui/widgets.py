"""
Small cross-platform UI widgets.
"""
import tkinter as tk


class ColorButton(tk.Label):
    """
    A Label-based button that honors bg/fg colors on every platform.

    Native tk.Button widgets on macOS (Aqua) ignore the background color,
    so colored action buttons (green START, red STOP) render as plain gray.
    A Label honors colors everywhere; this subclass adds button behavior:
    a click command, pressed feedback, and the disabled state.

    Click handling is deliberately simple and robust: the command fires on
    mouse release whenever the release lands inside the widget. Visual
    feedback (pressed relief) is best-effort and never gates the command —
    on macOS, reconfiguring a Label mid-click can emit spurious Enter/Leave
    events, and any logic that depends on that state silently drops clicks.

    Supports the tk.Button options used in this app: text, bg/fg, font,
    relief, padx/pady, state, activebackground, activeforeground.
    """

    def __init__(self, master=None, command=None, **kwargs):
        kwargs.setdefault('relief', tk.RAISED)
        kwargs.setdefault('borderwidth', 1)
        kwargs.setdefault('padx', 10)
        kwargs.setdefault('pady', 4)
        # Keep the normal arrow cursor (no hand cursor)
        kwargs.pop('cursor', None)
        # Hover recoloring is dropped: on macOS it caused redraw-induced
        # Enter/Leave churn. Keep a single stable appearance.
        kwargs.pop('activebackground', None)
        kwargs.pop('activeforeground', None)

        self._normal_relief = kwargs['relief']
        super().__init__(master, **kwargs)
        self.command = command

        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)

    def _is_disabled(self) -> bool:
        return str(self['state']) == tk.DISABLED

    def _on_press(self, _event) -> None:
        if self._is_disabled():
            return
        # Best-effort pressed feedback only; does not affect firing
        try:
            self.configure(relief=tk.SUNKEN)
        except tk.TclError:
            pass

    def _on_release(self, event) -> None:
        try:
            self.configure(relief=self._normal_relief)
        except tk.TclError:
            pass
        if self._is_disabled():
            return
        # Fire whenever the release lands inside the widget. No dependency
        # on press/enter/leave state, which is unreliable on macOS.
        if (0 <= event.x < self.winfo_width()
                and 0 <= event.y < self.winfo_height()
                and self.command):
            self.command()
