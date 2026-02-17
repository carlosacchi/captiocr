"""
Selection window for choosing capture area.
"""
import tkinter as tk
from typing import Optional, Callable, Tuple
import logging

from .base_window import BaseWindow
from ..config.constants import SELECTION_WINDOW_ALPHA, SELECTION_WINDOW_COLOR, MIN_CAPTURE_AREA_SIZE


class SelectionWindow(BaseWindow):
    """Fullscreen overlay window for area selection across multiple monitors."""
    
    def __init__(self, parent: tk.Tk, monitor_manager=None, settings=None):
        """Initialize selection window."""
        super().__init__(parent, "Area Selection")
        
        # Monitor management
        self.monitor_manager = monitor_manager
        self.settings = settings
        
        # Selection state
        self.start_x: Optional[int] = None
        self.start_y: Optional[int] = None
        self.rect_id: Optional[int] = None
        self.selection_area: Optional[Tuple[int, int, int, int]] = None
        
        # Callbacks
        self.on_selection_complete: Optional[Callable[[Tuple[int, int, int, int]], None]] = None
        self.on_selection_cancelled: Optional[Callable[[], None]] = None
        
        # Get virtual desktop dimensions
        if self.monitor_manager:
            self.virtual_bounds = self.monitor_manager.get_virtual_screen_bounds()
            self.logger.info(f"Virtual desktop: {self.virtual_bounds}")
            self.logger.info(f"Found {self.monitor_manager.get_monitor_count()} monitor(s)")
        else:
            # Fallback to single monitor
            parent.update()
            self.virtual_bounds = (0, 0, parent.winfo_screenwidth(), parent.winfo_screenheight())
            self.logger.warning("No monitor manager available, using single monitor fallback")
        
        # For backward compatibility, set screen dimensions
        self.screen_width = self.virtual_bounds[2]  # width
        self.screen_height = self.virtual_bounds[3]  # height
        
        # Don't set a default scale factor - we'll get the correct one per-monitor from settings
        self.scale_factor = None
        
        self.logger.info(f"Selection window will cover: {self.virtual_bounds}")
        if self.monitor_manager:
            self.logger.info(f"Per-monitor DPI scaling will be used")
        else:
            self.logger.info(f"Fallback DPI scale factor: 1.0")
    
    def show(self) -> None:
        """Show the selection window."""
        # Create fullscreen window
        self.create_window()
        
        # Configure window to cover virtual desktop
        x, y, width, height = self.virtual_bounds
        
        self.window.attributes('-fullscreen', False)  # Don't use fullscreen mode
        self.window.attributes('-alpha', SELECTION_WINDOW_ALPHA)
        self.window.attributes('-topmost', True)
        self.window.overrideredirect(True)
        self.window.configure(bg=SELECTION_WINDOW_COLOR)
        
        # Set geometry to cover virtual desktop (all monitors)
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Create canvas
        self.canvas = tk.Canvas(
            self.window,
            highlightthickness=0,
            bg=SELECTION_WINDOW_COLOR,
            cursor='cross'
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events
        self.canvas.bind('<ButtonPress-1>', self._on_mouse_down)
        self.canvas.bind('<B1-Motion>', self._on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_mouse_up)
        
        # IMPORTANTE: Bind su window, non su self
        self.window.bind('<Return>', self._on_confirm)
        self.window.bind('<Escape>', self._on_cancel)
        
        # Aggiungi anche binding del tasto destro per cancel
        self.window.bind('<Button-3>', self._on_cancel)  # Click destro
        
        # Add instructions
        self._add_instructions()
        
        # Protocol handler for window close (may not work with overrideredirect)
        try:
            self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)
        except Exception as e:
            self.logger.debug(f"Could not set WM_DELETE_WINDOW protocol: {e}")
        
        # Force focus on window (like original)
        self.window.lift()
        self.window.focus_force()
        
        # Don't use grab_set() as it can interfere with key events
        # Update window and give focus time to settle
        self.window.update()
        self.window.after(100, lambda: self.window.focus_force())
        
        # Show window
        super().show()
    
    def _add_instructions(self) -> None:
        """Add instruction text to the window."""
        instructions = """Click and drag to select capture area.
Press ESC to cancel.
Press Enter to confirm selection."""
        
        if self.monitor_manager:
            # Add instructions for each monitor
            for monitor in self.monitor_manager.monitors:
                label = tk.Label(
                    self.window,
                    text=instructions,
                    bg='yellow',
                    font=('Arial', 12),
                    justify=tk.CENTER
                )
                
                # Position at bottom of each monitor, adjusted for virtual screen offset
                label_x = monitor.x + monitor.width // 2 - self.virtual_bounds[0]
                label_y = monitor.y + monitor.height - 50 - self.virtual_bounds[1]
                
                label.place(x=label_x, y=label_y, anchor=tk.S)
            
            # Add cancel button on primary monitor
            primary = self.monitor_manager.get_primary_monitor()
            if primary:
                btn_x = primary.x + primary.width - 100 - self.virtual_bounds[0]
                btn_y = primary.y + 20 - self.virtual_bounds[1]
                
                cancel_button = tk.Button(
                    self.window,
                    text="Cancel (ESC)",
                    command=self._on_cancel,
                    bg='red',
                    fg='white',
                    font=('Arial', 10, 'bold'),
                    cursor='hand2'
                )
                cancel_button.place(x=btn_x, y=btn_y)
        else:
            # Fallback for single monitor
            self.instruction_label = tk.Label(
                self.window,
                text=instructions,
                bg='yellow',
                font=('Arial', 12),
                justify=tk.CENTER
            )
            self.instruction_label.place(relx=0.5, rely=0.95, anchor=tk.S)
            
            cancel_button = tk.Button(
                self.window,
                text="Cancel (ESC)",
                command=self._on_cancel,
                bg='red',
                fg='white',
                font=('Arial', 10, 'bold'),
                cursor='hand2'
            )
            cancel_button.place(relx=0.95, rely=0.05, anchor=tk.NE)
    
    def _on_mouse_down(self, event) -> None:
        """Handle mouse button press."""
        # Convert canvas coordinates to screen coordinates  
        screen_x = event.x + self.virtual_bounds[0]
        screen_y = event.y + self.virtual_bounds[1]
        
        self.start_x = screen_x
        self.start_y = screen_y
        
        # Delete any existing rectangle
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        
        # Create new rectangle (use canvas coordinates for drawing)
        self.rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline='red', width=2, tags="selection"
        )
        
        # Log which monitor the selection started on
        if self.monitor_manager:
            monitor = self.monitor_manager.get_monitor_from_point(screen_x, screen_y)
            if monitor:
                self.logger.info(f"Selection started on {monitor.name} at ({screen_x}, {screen_y})")
                self.logger.info(f"Monitor info: bounds={monitor.bounds}, DPI={monitor.dpi}, Scale={monitor.scale_factor}")
        else:
            self.logger.info(f"Selection started at: ({screen_x}, {screen_y})")
    
    def _on_mouse_drag(self, event) -> None:
        """Handle mouse drag."""
        if self.rect_id and self.start_x is not None:
            # Convert start position to canvas coordinates
            start_canvas_x = self.start_x - self.virtual_bounds[0]
            start_canvas_y = self.start_y - self.virtual_bounds[1]
            
            # Update rectangle
            self.canvas.coords(
                self.rect_id,
                start_canvas_x, start_canvas_y, event.x, event.y
            )
            
            # Add fill for better visibility
            self.canvas.itemconfig(
                self.rect_id,
                fill='red', stipple='gray50'
            )
    
    def _on_mouse_up(self, event) -> None:
        """Handle mouse button release."""
        if self.rect_id and self.start_x is not None and self.start_y is not None:
            # Convert to screen coordinates
            end_x = event.x + self.virtual_bounds[0]
            end_y = event.y + self.virtual_bounds[1]
            
            # Calculate final coordinates in screen space
            x1 = min(self.start_x, end_x)
            y1 = min(self.start_y, end_y)
            x2 = max(self.start_x, end_x)
            y2 = max(self.start_y, end_y)
            
            # Update rectangle appearance
            self.canvas.itemconfig(
                self.rect_id,
                outline='green', width=3
            )
            
            # Store selection in screen coordinates
            self.selection_area = (x1, y1, x2, y2)
            
            # Log selection info
            if self.monitor_manager:
                monitor = self.monitor_manager.get_monitor_from_point(x1, y1)
                if monitor:
                    self.logger.debug(f"Selection ended on {monitor.name}: {self.selection_area}")
            else:
                self.logger.debug(f"Selection ended at: ({end_x}, {end_y})")
                self.logger.debug(f"Selection area: {self.selection_area}")
    
    def _on_confirm(self, event=None) -> None:
        """Handle selection confirmation."""
        if not self.selection_area:
            return

        x1, y1, x2, y2 = self.selection_area
        
        # Calculate sizes in logical pixels
        logical_width, logical_height = x2 - x1, y2 - y1
        
        # Use scale factor from monitor manager or settings based on coordinates
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        
        if self.monitor_manager:
            # Prefer monitor manager for accurate per-monitor DPI
            scale_factor = self.monitor_manager.get_scale_factor_for_point(center_x, center_y)
            self.logger.info(f"Using scale factor {scale_factor} from monitor manager for center coordinates ({center_x}, {center_y})")
        elif self.settings:
            # Fallback to settings if no monitor manager available
            scale_factor = self.settings.get_scale_factor_for_coordinates(center_x, center_y)
            self.logger.info(f"Using scale factor {scale_factor} from settings based on center coordinates ({center_x}, {center_y})")
        else:
            scale_factor = 1.0
            self.logger.info(f"No monitor manager or settings available, using default scale factor 1.0")
        
        # With DPI awareness enabled, coordinates are already in physical pixels
        # We don't need to apply scale factor for ImageGrab
        capture_area = (x1, y1, x2, y2)
        
        # Calculate physical size for validation (already in physical pixels)
        physical_width = logical_width  # These are actually physical pixels now
        physical_height = logical_height
        
        # Validate minimum size
        if physical_width < MIN_CAPTURE_AREA_SIZE or physical_height < MIN_CAPTURE_AREA_SIZE:
            err = self.canvas.create_text(
                self.screen_width // 2,
                self.screen_height // 2,
                text=f"Selected area too small!\nMinimum {MIN_CAPTURE_AREA_SIZE}×{MIN_CAPTURE_AREA_SIZE} pixels\nYour selection: {physical_width}×{physical_height} pixels",
                fill='red', font=('Arial', 16, 'bold'), tags="error"
            )
            self.window.after(3000, lambda: self.canvas.delete("error"))
            return
        
        self.logger.info(
            f"Selection confirmed:\n"
            f"  Screen coords: {self.selection_area}\n"
            f"  Capture area: {capture_area}\n"
            f"  Detected scale factor: {scale_factor:.2f} (not applied due to DPI awareness)"
        )

        # Hide window so it doesn't appear in capture
        try:
            self.window.grab_release()
        except Exception as e:
            self.logger.debug(f"Could not release grab (may not have been set): {e}")
        self.window.withdraw()

        # Fire the callback with coordinates (already physical due to DPI awareness)
        if self.on_selection_complete:
            self.on_selection_complete(capture_area, scale_factor)

        # Clean up after a moment
        self.window.after(50, self.destroy)

    def _on_cancel(self, event=None) -> None:
        """Handle selection cancellation."""
        self.logger.info("Selection cancelled")
        
        try:
            # Hide window first
            if self.window:
                self.window.withdraw()
            
            # Call the callback before destroying (like original)
            if self.on_selection_cancelled:
                self.on_selection_cancelled()
            
            # Then destroy the window after a short delay
            if self.window:
                self.window.after(10, self.destroy)
            
        except Exception as e:
            self.logger.error(f"Error in cancel: {e}")
            # Force destruction on error
            try:
                if self.window:
                    self.window.destroy()
                    self.window = None
            except:
                pass