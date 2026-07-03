"""
Capture window overlay for showing capture area.
"""
import sys
import tkinter as tk
from typing import Optional, Callable, Tuple

from .base_window import BaseWindow
from .widgets import ColorButton
from ..config.constants import (
    CAPTURE_WINDOW_ALPHA, CAPTURE_WINDOW_COLOR, CONTROL_FRAME_HEIGHT,
    CAPTURE_OVERLAY_ALPHA_MACOS
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
        # Stop button state
        self._press_on_stop = False
        self._stop_requested = False
        # Callbacks
        self.on_stop: Optional[Callable[[], None]] = None
        self.on_position_changed: Optional[Callable[[Tuple[int,int,int,int]],None]] = None

    def _point_on_stop_button(self, x_root: int, y_root: int) -> bool:
        """
        Check whether an absolute screen point falls on the STOP button.

        Hit-testing by screen rectangle instead of by the widget that Tk
        delivered the event to: in a transparent overrideredirect overlay
        on macOS, clicks on parts of the button can be routed to the
        underlying frame, making the button feel unclickable.
        """
        button = getattr(self, 'stop_button', None)
        if not button or not self._window_exists():
            return False
        try:
            bx, by = button.winfo_rootx(), button.winfo_rooty()
            return (bx <= x_root < bx + button.winfo_width()
                    and by <= y_root < by + button.winfo_height())
        except Exception:
            return False

    def show(self) -> None:
        """Show the capture window."""
        # Create window
        self.create_window()
        
        # Configure window
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)

        # On macOS use true per-pixel transparency: the capture area stays
        # fully clear (no white film over the captions, better OCR) while
        # the control bar and STOP button remain fully opaque and readable.
        self._true_transparency = False
        if sys.platform == 'darwin':
            try:
                self.window.attributes('-transparent', True)
                self.window.configure(bg='systemTransparent')
                # Soften the visible parts (control bar, border): window
                # alpha multiplies with the per-pixel transparency, so the
                # capture area itself stays fully clear
                self.window.attributes('-alpha', CAPTURE_OVERLAY_ALPHA_MACOS)
                self._true_transparency = True
            except tk.TclError as e:
                self.logger.debug(f"True transparency unavailable: {e}")
        if not self._true_transparency:
            self.window.attributes('-alpha', CAPTURE_WINDOW_ALPHA)
            self.window.configure(bg=CAPTURE_WINDOW_COLOR)
        
        # Calculate window position and size
        # With DPI awareness enabled, coordinates are already in logical pixels
        x1, y1, x2, y2 = self.capture_area
        screen_x      = int(x1)
        screen_y      = int(y1)
        screen_width  = int(x2 - x1)
        screen_height = int(y2 - y1)
        
        # Add space for control frame above the capture area
        # CONTROL_FRAME_HEIGHT is already in logical pixels
        control_frame_height = int(CONTROL_FRAME_HEIGHT)
        total_height = screen_height + control_frame_height
        
        # Position the window so control frame is above the original capture area
        window_y = screen_y - control_frame_height

        self.logger.debug(f"Capture window: selection={self.capture_area}, size={screen_width}x{screen_height}, "
                         f"control_height={control_frame_height}, total={screen_width}x{total_height}, "
                         f"position=({screen_x},{window_y}), scale={self.scale_factor}")

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
        
        # Focus
        self.window.focus_force()
        
        # Windows 11 workaround: start periodic topmost refresh (removed event bindings that caused infinite loops)
        self.window.after(2000, self._refresh_topmost)
        
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
            text="Capturing... (Click and drag to move)",
            bg='blue',
            fg='white',
            font=('Arial', 9)
        )
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Stop button (ColorButton: honors the red bg on macOS too)
        self.stop_button = ColorButton(
            self.control_frame,
            text="STOP",
            command=self._on_stop_clicked,
            bg='red',
            fg='white',
            font=('Arial', 9, 'bold'),
            relief=tk.FLAT,
            padx=10,
            pady=1
        )
        self.stop_button.pack(side=tk.RIGHT, padx=8, pady=1)
    
    def _create_capture_frame(self) -> None:
        """Create the capture area frame (transparent with border)."""
        # Use a Canvas to draw just the border
        canvas_bg = 'systemTransparent' if self._true_transparency else CAPTURE_WINDOW_COLOR
        self.capture_frame = tk.Canvas(
            self.window,
            bg=canvas_bg,
            highlightthickness=0
        )
        self.capture_frame.pack(fill=tk.BOTH, expand=True)
        
        # Draw border rectangle after window is displayed
        self.window.after(10, self._draw_border)
    
    def _draw_border(self) -> None:
        """Draw a border rectangle on the canvas."""
        if hasattr(self, 'capture_frame') and self._window_exists():
            # Get canvas dimensions
            self.capture_frame.update_idletasks()
            width = self.capture_frame.winfo_width()
            height = self.capture_frame.winfo_height()
            
            self.logger.debug(f"Capture frame canvas size: {width} x {height}")
            
            # Draw rectangle border (2 pixels from edge to ensure visibility)
            self.capture_frame.create_rectangle(
                2, 2, width-2, height-2,
                outline='red',
                width=3,
                fill=''  # No fill, just border
            )
    
    def _on_drag_start(self, event) -> None:
        """Handle start of window drag."""
        # Window-level bindings also fire for clicks on child widgets. A
        # press on the STOP button's screen rectangle must not start a
        # window drag; remember it and let the release decide (hit-testing
        # by widget is unreliable in transparent overlays on macOS, so we
        # test by coordinates as a fallback for the button's own handler).
        if self._point_on_stop_button(event.x_root, event.y_root):
            self._press_on_stop = True
            return
        self._press_on_stop = False
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

        # Click started on the STOP button: a release still on it is a
        # stop click (fallback for when Tk routed the click to the frame
        # instead of the button widget). The button's own handler and the
        # _stop_requested guard make sure stop only fires once.
        if self._press_on_stop:
            self._press_on_stop = False
            if self._point_on_stop_button(event.x_root, event.y_root):
                self._on_stop_clicked()
            return

        # No drag in progress
        if self.drag_start_x is None and self.drag_start_y is None:
            return

        # Get current window position
        current_x = self.window.winfo_x()
        current_y = self.window.winfo_y()
        current_width = self.window.winfo_width()
        current_height = self.window.winfo_height()
        
        # Re-apply topmost after drag operation
        self.window.attributes('-topmost', True)
        self.window.lift()
        
        # Calculate the actual capture area (excluding control frame)
        control_frame_height = int(CONTROL_FRAME_HEIGHT)
        
        # The capture area starts below the control frame
        capture_x = current_x
        capture_y = current_y + control_frame_height
        capture_width = current_width
        capture_height = current_height - control_frame_height
        
        # With DPI awareness, coordinates are already in correct format for ImageGrab
        abs_x1 = int(capture_x)
        abs_y1 = int(capture_y)
        abs_x2 = abs_x1 + int(capture_width)
        abs_y2 = abs_y1 + int(capture_height)
        
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
        # Both the button's own handler and the window-level fallback can
        # detect the same click — only act on the first one
        if self._stop_requested:
            return
        self._stop_requested = True
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
    
    def _refresh_topmost(self) -> None:
        """Periodically refresh topmost status to handle Windows 11 issues."""
        if self._window_exists():
            try:
                # Simply re-assert topmost without the flip trick (which can cause issues)
                self.window.attributes('-topmost', True)
                # Schedule next refresh every 3000ms (less aggressive)
                self.window.after(3000, self._refresh_topmost)
            except Exception:
                pass