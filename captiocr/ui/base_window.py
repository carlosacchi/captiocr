"""
Base window class for UI windows.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Tuple
import logging
import gc


class BaseWindow:
    """Base class for all UI windows with common functionality."""
    
    def __init__(self, parent: Optional[tk.Tk] = None, title: str = "Window"):
        """
        Initialize base window.
        
        Args:
            parent: Parent window
            title: Window title
        """
        self.logger = logging.getLogger(f'CaptiOCR.{self.__class__.__name__}')
        self.parent = parent
        self.window: Optional[tk.Toplevel] = None
        self.title = title
        self._destroyed = False
    
    def create_window(self, **kwargs) -> tk.Toplevel:
        """
        Create the window with standard settings.
        
        Args:
            **kwargs: Additional window attributes
            
        Returns:
            Created window
        """
        if self.window and self._window_exists():
            self.logger.warning("Window already exists")
            return self.window
        
        if self.parent:
            self.window = tk.Toplevel(self.parent)
        else:
            self.window = tk.Tk()
        
        self.window.title(self.title)
        
        # Apply any additional attributes
        for key, value in kwargs.items():
            if hasattr(self.window, key):
                setattr(self.window, key, value)
            elif key.startswith('-'):
                # Handle window attributes like '-alpha'
                self.window.attributes(key, value)
        
        # Set up close protocol
        self.window.protocol("WM_DELETE_WINDOW", self.destroy)
        
        self._destroyed = False
        self.logger.debug(f"Window created: {self.title}")
        
        return self.window
    
    def _window_exists(self) -> bool:
        """
        Check if window exists and is valid.
        
        Returns:
            True if window exists
        """
        if not self.window or self._destroyed:
            return False
        
        try:
            return self.window.winfo_exists()
        except Exception:
            return False
    
    def destroy(self) -> None:
        """Safely destroy the window."""
        if self._destroyed:
            return
        
        self._destroyed = True
        
        if self.window and self._window_exists():
            try:
                # Unbind all events
                for event in self.window.bind():
                    self.window.unbind(event)
                
                # Destroy all children
                for widget in self.window.winfo_children():
                    widget.destroy()
                
                # Destroy the window
                self.window.destroy()
                self.logger.debug(f"Window destroyed: {self.title}")
                
            except Exception as e:
                self.logger.error(f"Error destroying window: {e}")
            finally:
                self.window = None
                gc.collect()
    
    def center_window(self, width: int, height: int) -> None:
        """
        Center the window on screen.
        
        Args:
            width: Window width
            height: Window height
        """
        if not self._window_exists():
            return
        
        # Get screen dimensions
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # Calculate position
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # Set geometry
        self.window.geometry(f"{width}x{height}+{x}+{y}")
    
    def show(self) -> None:
        """Show the window."""
        if self._window_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
    
    def hide(self) -> None:
        """Hide the window."""
        if self._window_exists():
            self.window.withdraw()
    
    def set_position(self, x: int, y: int) -> None:
        """
        Set window position.
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        if self._window_exists():
            self.window.geometry(f"+{x}+{y}")
    
    def get_position(self) -> Tuple[int, int]:
        """
        Get window position.
        
        Returns:
            Tuple of (x, y) coordinates
        """
        if self._window_exists():
            return self.window.winfo_x(), self.window.winfo_y()
        return 0, 0
    
    def bind_event(self, event: str, handler: callable) -> None:
        """
        Bind an event to the window.
        
        Args:
            event: Event string
            handler: Event handler function
        """
        if self._window_exists():
            self.window.bind(event, handler)
    
    def unbind_event(self, event: str) -> None:
        """
        Unbind an event from the window.
        
        Args:
            event: Event string
        """
        if self._window_exists():
            try:
                self.window.unbind(event)
            except Exception:
                pass