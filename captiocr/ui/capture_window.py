"""
Capture window overlay for showing capture area.
"""
import tkinter as tk
from typing import Optional, Callable, Tuple
import logging

from .base_window import BaseWindow
from ..config.constants import (
    CAPTURE_WINDOW_ALPHA, CAPTURE_WINDOW_COLOR, CONTROL_FRAME_HEIGHT
)
    
class CaptureWindow(BaseWindow):
    def __init__(self,
                parent: tk.Tk,
                capture_area: Tuple[int, int, int, int],
                scale_factor: float):
        super().__init__(parent, "Capture Area")
        self.capture_area = capture_area
        self.scale_factor = scale_factor
        # Drag state
        self.drag_start_x: Optional[int] = None
        self.drag_start_y: Optional[int] = None
        # Callbacks
        self.on_stop: Optional[Callable[[], None]] = None
        self.on_position_changed: Optional[Callable[[Tuple[int,int,int,int]],None]] = None
    
    def _detect_dpi_scaling(self) -> float:
        """Detect screen DPI scaling factor."""
        try:
            scale = self.parent.tk.call('tk', 'scaling')
            return scale / 96.0 if scale > 0 else 1.0
        except:
            return 1.0
    
    def show(self) -> None:
        """Show the capture window."""
        # Create window
        self.create_window()
        
        # Configure window
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', CAPTURE_WINDOW_ALPHA)
        self.window.configure(bg=CAPTURE_WINDOW_COLOR)
        
        # Calculate window position and size
        x1, y1, x2, y2 = self.capture_area
        screen_x      = int(x1 / self.scale_factor)
        screen_y      = int(y1 / self.scale_factor)
        screen_width  = int((x2 - x1) / self.scale_factor)
        screen_height = int((y2 - y1) / self.scale_factor)
        
        # Add space for control frame above the capture area
        # CONTROL_FRAME_HEIGHT is in logical pixels, convert to screen pixels
        control_frame_screen_height = int(CONTROL_FRAME_HEIGHT)
        total_height = screen_height + control_frame_screen_height
        
        # Position the window so control frame is above the original capture area
        window_y = screen_y - control_frame_screen_height
        
        print(f"=== CAPTURE WINDOW DEBUG ===")
        print(f"Capture area (scaled for ImageGrab): {self.capture_area}")
        print(f"Scale factor: {self.scale_factor}")
        print(f"Control frame height (screen): {control_frame_screen_height}")
        print(f"Window position: {screen_x}, {window_y}")
        print(f"Window size: {screen_width} x {total_height}")
        
        # Set geometry - window extends above the original capture area
        self.window.geometry(f"{screen_width}x{total_height}+{screen_x}+{window_y}")
        
        # Create control frame at the top
        self._create_control_frame()
        
        # Create capture area frame below the control frame
        self._create_capture_frame()
        
        # Bind drag events
        self.window.bind('<Button-1>', self._on_drag_start)
        self.window.bind('<B1-Motion>', self._on_drag_motion)
        self.window.bind('<ButtonRelease-1>', self._on_drag_end)
        
        # Make window visible
        self.window.update_idletasks()
        self.window.deiconify()
        self.window.lift()
        self.window.attributes('-topmost', True)
        
        # Focus and bind hotkeys
        self.window.focus_force()
        self.window.bind_all('<Control-q>', lambda e: self._on_stop_clicked())
        
        self.logger.info(f"Capture window shown at {screen_x},{window_y} size {screen_width}x{total_height}")
    
    def _create_control_frame(self) -> None:
        """Create control frame with status and stop button."""
        self.control_frame = tk.Frame(
            self.window,
            bg='blue',
            height=CONTROL_FRAME_HEIGHT
        )
        self.control_frame.pack(fill=tk.X, side=tk.TOP)
        
        # Status label
        self.status_label = tk.Label(
            self.control_frame,
            text="Capturing...\n(Click and drag to move)",
            bg='blue',
            fg='white',
            font=('Arial', 10)
        )
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Stop button
        self.stop_button = tk.Button(
            self.control_frame,
            text="STOP",
            command=self._on_stop_clicked,
            bg='red',
            fg='white',
            font=('Arial', 10, 'bold'),
            relief=tk.FLAT,
            cursor='hand2'
        )
        self.stop_button.pack(side=tk.RIGHT, padx=10, pady=2)
    
    def _create_capture_frame(self) -> None:
        """Create the capture area frame (yellow background)."""
        self.capture_frame = tk.Frame(
            self.window,
            bg=CAPTURE_WINDOW_COLOR
        )
        self.capture_frame.pack(fill=tk.BOTH, expand=True)
    
    def _on_drag_start(self, event) -> None:
        """Handle start of window drag."""
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.logger.debug(f"Drag started at ({event.x}, {event.y})")
    
    def _on_drag_motion(self, event) -> None:
        """Handle window drag motion."""
        if self.drag_start_x is not None and self.drag_start_y is not None:
            # Calculate new position
            x = self.window.winfo_x() + (event.x - self.drag_start_x)
            y = self.window.winfo_y() + (event.y - self.drag_start_y)
            
            # Move window
            self.window.geometry(f"+{x}+{y}")
    
    def _on_drag_end(self, event) -> None:
        """Handle end of window drag."""
        if not self._window_exists():
            return
        
        # Get current window position
        current_x = self.window.winfo_x()
        current_y = self.window.winfo_y()
        current_width = self.window.winfo_width()
        current_height = self.window.winfo_height()
        
        # Calculate the actual capture area (excluding control frame)
        control_frame_screen_height = int(CONTROL_FRAME_HEIGHT)
        
        # The capture area starts below the control frame
        capture_screen_x = current_x
        capture_screen_y = current_y + control_frame_screen_height
        capture_screen_width = current_width
        capture_screen_height = current_height - control_frame_screen_height
        
        # Convert capture area back to absolute coordinates for ImageGrab
        abs_x1 = int(capture_screen_x * self.scale_factor)
        abs_y1 = int(capture_screen_y * self.scale_factor)
        abs_x2 = abs_x1 + int(capture_screen_width * self.scale_factor)
        abs_y2 = abs_y1 + int(capture_screen_height * self.scale_factor)
        
        # Update capture area
        self.capture_area = (abs_x1, abs_y1, abs_x2, abs_y2)
        
        # Notify callback with the new capture area
        if self.on_position_changed:
            self.on_position_changed(self.capture_area)
        
        # Reset drag state
        self.drag_start_x = None
        self.drag_start_y = None
        
        self.logger.debug(f"Window moved to {current_x},{current_y}, capture area: {self.capture_area}")
    
    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        self.logger.info("Stop button clicked")
        # Immediately hide ourselves so nothing remains onscreen
        if self.window and self._window_exists():
            self.window.withdraw()
        # Then notify MainWindow to fully stop & destroy
        if self.on_stop:
            self.on_stop()
    
    def update_status(self, text: str) -> None:
        """
        Update status label text.
        
        Args:
            text: New status text
        """
        if self._window_exists() and hasattr(self, 'status_label'):
            self.status_label.config(text=text)