"""
Base class for standardized dialog windows.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable


class DialogBase:
    """Base class for creating standardized dialog windows."""
    
    def __init__(self, parent: tk.Tk, title: str, width: int = 400, height: int = 300):
        """
        Initialize dialog base.
        
        Args:
            parent: Parent window
            title: Dialog title
            width: Dialog width in pixels
            height: Dialog height in pixels
        """
        self.parent = parent
        self.dialog: Optional[tk.Toplevel] = None
        self.result = None
        self._title = title
        self._width = width
        self._height = height
    
    def create_dialog(self) -> tk.Toplevel:
        """
        Create and configure the dialog window.
        
        Returns:
            The created dialog window
        """
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(self._title)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Set size and center
        x = (self.dialog.winfo_screenwidth() - self._width) // 2
        y = (self.dialog.winfo_screenheight() - self._height) // 2
        self.dialog.geometry(f"{self._width}x{self._height}+{x}+{y}")
        
        return self.dialog
    
    def create_main_frame(self, padding: str = "20") -> ttk.Frame:
        """
        Create main frame with standard padding.
        
        Args:
            padding: Frame padding
            
        Returns:
            The created main frame
        """
        frame = ttk.Frame(self.dialog, padding=padding)
        frame.pack(fill=tk.BOTH, expand=True)
        return frame
    
    def create_title_label(self, frame: ttk.Frame, text: str) -> ttk.Label:
        """
        Create standard title label.
        
        Args:
            frame: Parent frame
            text: Title text
            
        Returns:
            The created title label
        """
        title_label = ttk.Label(
            frame,
            text=text,
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(0, 15))
        return title_label
    
    def create_button_frame(self, frame: ttk.Frame) -> ttk.Frame:
        """
        Create standard button frame.
        
        Args:
            frame: Parent frame
            
        Returns:
            The created button frame
        """
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        return button_frame
    
    def add_ok_cancel_buttons(self, button_frame: ttk.Frame, 
                             ok_text: str = "OK", 
                             ok_callback: Optional[Callable] = None,
                             cancel_text: str = "Cancel",
                             ok_width: int = 10) -> tuple:
        """
        Add standard OK/Cancel buttons.
        
        Args:
            button_frame: Frame to add buttons to
            ok_text: Text for OK button
            ok_callback: Callback for OK button (if None, uses simple close)
            cancel_text: Text for Cancel button
            ok_width: Width of buttons
            
        Returns:
            Tuple of (ok_button, cancel_button)
        """
        ok_button = ttk.Button(
            button_frame,
            text=ok_text,
            command=ok_callback if ok_callback else self.close_dialog,
            width=ok_width
        )
        ok_button.pack(side=tk.LEFT, padx=(0, 10))
        
        cancel_button = ttk.Button(
            button_frame,
            text=cancel_text,
            command=self.close_dialog,
            width=ok_width
        )
        cancel_button.pack(side=tk.LEFT)
        
        return ok_button, cancel_button
    
    def close_dialog(self) -> None:
        """
        Standard method to close the dialog.
        Can be overridden for custom cleanup.
        """
        if self.dialog:
            self.dialog.destroy()
    
    def show_and_wait(self) -> any:
        """
        Show dialog and wait for user interaction.
        
        Returns:
            The result value set by the dialog
        """
        if self.dialog:
            self.parent.wait_window(self.dialog)
        return self.result