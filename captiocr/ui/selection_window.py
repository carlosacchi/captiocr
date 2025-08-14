"""
Selection window for choosing capture area.
"""
import tkinter as tk
from typing import Optional, Callable, Tuple
import logging

from .base_window import BaseWindow
from ..config.constants import SELECTION_WINDOW_ALPHA, SELECTION_WINDOW_COLOR


class SelectionWindow(BaseWindow):
    """Fullscreen overlay window for area selection."""
    
    def __init__(self, parent: tk.Tk):
        """Initialize selection window."""
        super().__init__(parent, "Area Selection")
        
        # Selection state
        self.start_x: Optional[int] = None
        self.start_y: Optional[int] = None
        self.rect_id: Optional[int] = None
        self.selection_area: Optional[Tuple[int, int, int, int]] = None
        
        # Callbacks
        self.on_selection_complete: Optional[Callable[[Tuple[int, int, int, int]], None]] = None
        self.on_selection_cancelled: Optional[Callable[[], None]] = None
        
        # Get screen dimensions and DPI scaling
        parent.update()  # Ensure window is drawn
        self.screen_width = parent.winfo_screenwidth()
        self.screen_height = parent.winfo_screenheight()
        
        print(f"Actual screen dimensions: {self.screen_width}x{self.screen_height}")
        
        self.scale_factor = self._detect_dpi_scaling()
        
        self.logger.info(f"Screen dimensions: {self.screen_width}x{self.screen_height}")
        self.logger.info(f"DPI scale factor: {self.scale_factor}")
    
    def _detect_dpi_scaling(self) -> float:
        """Detect screen DPI scaling factor."""
        try:
            print("Detecting DPI scaling...")
            
            # Method 1: Use ctypes on Windows (ESATTAMENTE COME L'ORIGINALE)
            try:
                import ctypes
                user32 = ctypes.windll.user32
                
                # Try to get DPI awareness first
                awareness = ctypes.c_int()
                error = ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
                
                if error == 0:  # S_OK
                    # Now get the actual scale factor
                    scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
                    print(f"Method 1: DPI scaling detected: {scale_factor}")
                    return scale_factor
            except Exception as e:
                print(f"Method 1 failed: {str(e)}")
            
            # Method 2: Use Tkinter's scaling
            try:
                # Get Tkinter's scaling factor
                scale_factor = self.parent.tk.call('tk', 'scaling')
                print(f"Method 2: Tkinter scaling: {scale_factor}")
                # Tkinter scaling is typically 96 DPI = 1.0
                # Convert to Windows scaling (where 96 DPI = 1.0, 120 DPI = 1.25, 144 DPI = 1.5)
                return scale_factor
            except Exception as e:
                print(f"Method 2 failed: {str(e)}")
            
            # Method 3: Use winfo_fpixels
            try:
                # Get the ratio of pixels per point
                scale_factor = self.parent.winfo_fpixels('1i') / 96.0
                print(f"Method 3: winfo_fpixels scaling: {scale_factor}")
                return scale_factor
            except Exception as e:
                print(f"Method 3 failed: {str(e)}")
                
            # If all methods fail, return a default value of 1.0
            print("All methods failed, using default scaling of 1.0")
            return 1.0
            
        except Exception as e:
            print(f"Critical error in detect_dpi_scaling: {str(e)}")
            return 1.0
    
    def show(self) -> None:
        """Show the selection window."""
        # Create fullscreen window
        self.create_window()
        
        # Configure window
        self.window.attributes('-fullscreen', True)
        self.window.attributes('-alpha', SELECTION_WINDOW_ALPHA)
        self.window.attributes('-topmost', True)
        self.window.overrideredirect(True)
        self.window.configure(bg=SELECTION_WINDOW_COLOR)
        
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
        
        # AGGIUNGI QUESTO: Protocol handler per chiusura (anche se con overrideredirect non sempre funziona)
        try:
            self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)
        except:
            pass
        
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
        
        self.instruction_label = tk.Label(
            self.window,
            text=instructions,
            bg='black',
            fg='white',
            font=('Arial', 12),
            justify=tk.CENTER
        )
        self.instruction_label.place(relx=0.5, rely=0.95, anchor=tk.S)
        
        # Aggiungi un pulsante Cancel
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
        self.start_x = event.x
        self.start_y = event.y
        
        # Delete any existing rectangle
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        
        # Create new rectangle
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline='red', width=1, tags="selection"
        )
        
        self.logger.debug(f"Selection started at: ({event.x}, {event.y})")
    
    def _on_mouse_drag(self, event) -> None:
        """Handle mouse drag."""
        if self.rect_id and self.start_x is not None:
            # Update rectangle
            self.canvas.coords(
                self.rect_id,
                self.start_x, self.start_y, event.x, event.y
            )
            
            # Add fill for better visibility
            self.canvas.itemconfig(
                self.rect_id,
                fill='red', stipple='gray50'
            )
    
    def _on_mouse_up(self, event) -> None:
        """Handle mouse button release."""
        if self.rect_id and self.start_x is not None and self.start_y is not None:
            # Calculate final coordinates
            x1 = min(self.start_x, event.x)
            y1 = min(self.start_y, event.y)
            x2 = max(self.start_x, event.x)
            y2 = max(self.start_y, event.y)
            
            # Update rectangle appearance
            self.canvas.itemconfig(
                self.rect_id,
                outline='green', width=3
            )
            
            # Store selection
            self.selection_area = (x1, y1, x2, y2)
            
            self.logger.debug(f"Selection ended at: ({event.x}, {event.y})")
            self.logger.debug(f"Selection area: {self.selection_area}")
    
    def _on_confirm(self, event=None) -> None:
        """Handle selection confirmation."""
        if not self.selection_area:
            return

        x1, y1, x2, y2 = self.selection_area
        sf = self.scale_factor

        # Debug
        print(f"Raw selection (logical pixels): {x1}, {y1}, {x2}, {y2}")
        print(f"Scale factor: {sf}")
        print(f"Logical size: {x2-x1}×{y2-y1} pixels")
        print(f"Physical size: {int((x2-x1)*sf)}×{int((y2-y1)*sf)} pixels")

        # Calculate sizes in both logical and physical pixels
        logical_width, logical_height = x2 - x1, y2 - y1
        physical_width = int(logical_width * sf)
        physical_height = int(logical_height * sf)
        
        # Validate minimum size using physical pixels (what actually gets captured)
        if physical_width < 100 or physical_height < 100:
            err = self.canvas.create_text(
                self.screen_width // 2,
                self.screen_height // 2,
                text=f"Selected area too small!\nMinimum 100×100 pixels\nYour selection: {physical_width}×{physical_height} pixels",
                fill='red', font=('Arial', 16, 'bold'), tags="error"
            )
            self.window.after(3000, lambda: self.canvas.delete("error"))
            return

        # **Scale up** to true device pixels for ImageGrab
        capture_area = (
            int(x1 * sf),
            int(y1 * sf),
            int(x2 * sf),
            int(y2 * sf),
        )
        self.logger.info(f"Selection confirmed – Display size: {logical_width}×{logical_height}  "
                        f"Physical size: {physical_width}×{physical_height}  "
                        f"Capture coords: {capture_area}")

        # Hide window so it doesn't appear in capture
        self.window.withdraw()

        # Fire the callback with the correctly scaled area
        if self.on_selection_complete:
            self.on_selection_complete(capture_area, sf)

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