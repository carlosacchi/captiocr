"""
Main application window.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import re
from datetime import datetime
from typing import Optional
import keyboard
from .selection_window import SelectionWindow
from .capture_window import CaptureWindow
from .dialogs import (SettingsDialog, LanguageDownloadDialog, IntervalConfigDialog,
                      PostProcessConfigDialog)
from ..core.ocr import OCRProcessor
from ..core.capture import ScreenCapture
from ..core.text_processor import TextProcessor
from ..config.settings import Settings
from ..config.constants import (
    APP_NAME, APP_VERSION, MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT,
    MAIN_WINDOW_ALPHA, SUPPORTED_LANGUAGES, MONITOR_REFRESH_ON_START
)
from ..utils.file_manager import FileManager
from ..utils.language_manager import LanguageManager
from ..utils.logger import get_logger
from ..utils.monitor_manager import MonitorManager
from captiocr.config.app_info import app_info

class MainWindow:
    """Main application window."""
    
    def __init__(self):
        """Initialize main window."""
        self.logger = get_logger('CaptiOCR.MainWindow')
        
        # Create root window
        self.root = tk.Tk()
        self.root.title(app_info.app_name)

        # Initialize components
        self._init_components()
        self._init_variables()
        self._init_ui()
        self._load_settings()
        
        # Set window properties
        self._configure_window()
        
        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.logger.info("Main window initialized")

        try:
            # Global hotkey: works even when the Tk app is not focused.
            # keyboard callbacks run on a background thread, so marshal to the
            # Tk main thread via root.after to avoid race conditions.
            keyboard.add_hotkey('ctrl+q', lambda: self.root.after(0, self._on_ctrl_q_toggle))
            self.logger.info("Registered global Ctrl+Q via keyboard.add_hotkey")
        except Exception as e:
            self.logger.error(f"Could not register global hotkey: {e}")
    
    def _on_ctrl_q_toggle(self, event=None):
        """Toggle capture: if idle, start selection→capture; if capturing, stop."""
        if not self.is_capturing:
            self._start_capture()
        else:
            # Invoke the CaptureWindow’s own stop-button logic,
            # which withdraws the overlay immediately before cleanup
            cw = getattr(self, 'capture_window', None)
            if cw and cw._window_exists():
                cw._on_stop_clicked()
    
    def _init_variables(self) -> None:
        """Initialize UI variables."""
        # UI variables
        self.selected_lang = tk.StringVar(value=SUPPORTED_LANGUAGES[0][0])
        self.status_var = tk.StringVar(value="Ready")
        self.interval_status_var = tk.StringVar(value="Interval: --")
        self.debug_enabled = tk.BooleanVar(value=False)
        self.use_caption_mode = tk.BooleanVar(value=True)  # Internal: True = Caption Mode
        self.use_document_mode = tk.BooleanVar(value=False)  # UI: False = Caption Mode default
        
        # State variables
        self.is_capturing = False
        self.capture_area: Optional[tuple] = None
        self._last_scale_factor: Optional[float] = None
    
    def _init_components(self) -> None:
        """Initialize application components."""
        # Settings
        self.settings = Settings()
        
        # Core components
        self.ocr_processor = OCRProcessor()
        self.text_processor = TextProcessor(
            self.settings.text_similarity_threshold,
            self.settings.capture_config.incremental_threshold
        )
        self.capture_config = self.settings.capture_config
        
        # Screen capture (will be updated with monitor manager after creation)
        self.screen_capture = ScreenCapture(
            self.ocr_processor,
            self.text_processor,
            self.capture_config
        )
        
        # Set callbacks
        self.screen_capture.on_text_captured = self._on_text_captured
        self.screen_capture.on_status_update = self._on_status_update
        self.capture_config.on_interval_change = self._on_interval_change
        
        # Managers
        self.file_manager = FileManager()
        self.language_manager = LanguageManager()
        self.monitor_manager = MonitorManager()
        
        # Set monitor manager in screen capture
        self.screen_capture.monitor_manager = self.monitor_manager
        
        # Windows
        self.selection_window: Optional[SelectionWindow] = None
        self.capture_window: Optional[CaptureWindow] = None
    
    
    def _init_ui(self) -> None:
        """Initialize user interface."""
        # Set transparency
        self.root.attributes('-alpha', MAIN_WINDOW_ALPHA)
        
        # Create menu
        self._create_menu()
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        
        # Add widgets
        self._create_widgets()
        
        # Create status bar
        self._create_status_bar()
    
    def _create_menu(self) -> None:
        """Create application menu."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Captures Folder", command=self._open_captures_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Save Settings", command=self._save_settings)
        file_menu.add_command(label="Load Settings", command=self._load_settings_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Open Log Folder", command=self._open_log_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_checkbutton(
            label="Enable Debug Logging",
            variable=self.debug_enabled,
            command=self._toggle_debug
        )
        settings_menu.add_checkbutton(
            label="Document Optimization",
            variable=self.use_document_mode,
            command=self._on_document_mode_toggle
        )
        settings_menu.add_separator()
        settings_menu.add_command(
            label="Configure Capture Interval...",
            command=self._configure_interval
        )
        settings_menu.add_command(
            label="Configure Post-Processing...",
            command=self._configure_post_processing
        )

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="Instructions", command=self._show_instructions)
    
    def _create_widgets(self) -> None:
        """Create main window widgets."""
        row = 0
        
        # Title
        title_label = ttk.Label(
            self.main_frame,
            text=APP_NAME,
            font=("Arial", 20, "bold")
        )
        title_label.grid(row=row, column=0, pady=5)
        row += 1
        
        # Version
        version_label = ttk.Label(
            self.main_frame,
            text=f"Version {APP_VERSION}",
            font=("Arial", 8)
        )
        version_label.grid(row=row, column=0, pady=5)
        row += 1
        
        # Language selection
        lang_frame = ttk.LabelFrame(
            self.main_frame,
            text="Select Language",
            padding="10"
        )
        lang_frame.grid(row=row, column=0, pady=5, sticky=(tk.W, tk.E))
        row += 1
        
        self.lang_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.selected_lang,
            values=[lang[0] for lang in SUPPORTED_LANGUAGES],
            state="readonly",
            width=20
        )
        self.lang_combo.pack(pady=5)
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language_changed)
        
        # Start/Stop button
        self.start_button = tk.Button(
            self.main_frame,
            text="START",
            command=self._toggle_capture,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 11, "bold"),
            relief=tk.FLAT,
            padx=20,
            pady=8,
            activebackground="#45a049",
            cursor="hand2"
        )
        self.start_button.grid(row=row, column=0, pady=8)
        row += 1
        
        # Status label
        self.status_label = ttk.Label(
            self.main_frame,
            textvariable=self.status_var,
            wraplength=220,
            justify='center'
        )
        self.status_label.grid(row=row, column=0, pady=5)
        row += 1
        
        # Captured text display
        text_frame = ttk.LabelFrame(
            self.main_frame,
            text="Captured Text",
            padding="10"
        )
        text_frame.grid(row=row, column=0, pady=8, sticky=(tk.W, tk.E))
        
        self.captured_text_display = ttk.Label(
            text_frame,
            text="Captured text will appear here",
            foreground='#888888',
            wraplength=200,
            justify='left'
        )
        self.captured_text_display.pack(pady=5, fill=tk.X, expand=True)
    
    def _create_status_bar(self) -> None:
        """Create status bar."""
        self.statusbar = ttk.Frame(self.root)
        self.statusbar.grid(row=999, column=0, sticky=(tk.W, tk.E))
        
        # Interval status
        self.interval_label = ttk.Label(
            self.statusbar,
            textvariable=self.interval_status_var,
            foreground='#555555'
        )
        self.interval_label.pack(side=tk.LEFT, padx=5, pady=2)
    
    def _configure_window(self) -> None:
        """Configure window properties."""
        # With DPI awareness, we need larger logical dimensions to get proper physical size
        # Increase base size to compensate for DPI scaling making windows appear smaller
        window_width = int(MAIN_WINDOW_WIDTH * 1.4)  # Make 40% larger
        window_height = int(MAIN_WINDOW_HEIGHT * 1.4)  # Make 40% larger
        
        self.logger.info(f"Setting window size: {window_width}x{window_height} (logical pixels, scaled from {MAIN_WINDOW_WIDTH}x{MAIN_WINDOW_HEIGHT})")
        
        # Set size and position
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.minsize(window_width, window_height)
        self.root.maxsize(window_width, window_height)
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - window_width) // 2
        y = (self.root.winfo_screenheight() - window_height) // 2
        self.root.geometry(f"+{x}+{y}")
        
        # Set icon if available
        self._set_window_icon()
    
    def _set_window_icon(self) -> None:
        """Set window icon."""
        try:
            icon_path = self.file_manager.get_resource_path("icon.ico")
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
                
            # Also try to set the smaller icon for title bar
            icon16_path = self.file_manager.get_resource_path("icon16.ico")
            if icon16_path.exists():
                self.root.iconbitmap(default=str(icon16_path))
                
        except Exception as e:
            self.logger.warning(f"Could not set window icon: {e}")
    
    def _load_settings(self) -> None:
        """Load application settings."""
        if self.settings.load_last_config():
            # Apply loaded settings
            self.selected_lang.set(self.settings.language)
            self.debug_enabled.set(self.settings.debug_enabled)
            self.use_caption_mode.set(self.settings.use_caption_mode)
            self.use_document_mode.set(not self.settings.use_caption_mode)
            self.text_processor.similarity_threshold = self.settings.text_similarity_threshold

            # Apply debug mode
            self.settings.apply_debug_mode()

            # Update interval display with loaded values
            self.interval_status_var.set(f"Interval: {self.settings.capture_config.min_capture_interval:.1f}s")
    
    def _toggle_capture(self) -> None:
        """Toggle between start and stop capture."""
        if not self.is_capturing:
            self._start_capture()
        else:
            # Use the same stop logic as the blue bar STOP button
            if self.capture_window and self.capture_window._window_exists():
                self.capture_window._on_stop_clicked()
    
    def _start_capture(self) -> None:
        """Start capture process."""
        try:
            self.logger.info("Starting capture process")
            
            # Refresh monitor information when START is pressed
            if MONITOR_REFRESH_ON_START:
                self.logger.info("Refreshing monitor configuration...")
                self.status_var.set("Detecting monitors...")
                self.root.update_idletasks()  # Update UI
                
                try:
                    if self.monitor_manager.refresh_monitors():
                        monitor_count = self.monitor_manager.get_monitor_count()
                        multi_monitor = self.monitor_manager.has_multi_monitor()
                        
                        self.logger.info(f"Monitor refresh complete: {monitor_count} monitor(s) detected")
                        
                        # Update settings with detected monitor configuration
                        self.settings.update_monitor_config(self.monitor_manager)
                        
                        # Save settings to persist monitor configuration
                        self.settings.save_last_config()
                        
                        if multi_monitor:
                            self.logger.info("Multi-monitor setup detected - selection will cover all monitors")
                        else:
                            self.logger.info("Single monitor setup detected")
                    else:
                        self.logger.warning("Monitor refresh failed, using defaults")
                        messagebox.showwarning(
                            "Monitor Detection", 
                            "Could not detect monitors properly. Using default settings.\n" +
                            "Selection may not work correctly on multi-monitor setups."
                        )
                except Exception as e:
                    self.logger.error(f"Error during monitor refresh: {e}")
                    messagebox.showerror(
                        "Monitor Detection Error",
                        f"Error detecting monitors: {str(e)}\n" +
                        "Continuing with single monitor mode."
                    )
            
            self.status_var.set("Select area and press Enter")
            
            # Create selection window with monitor manager and settings
            self.selection_window = SelectionWindow(self.root, self.monitor_manager, self.settings)
            self.selection_window.on_selection_complete = self._on_selection_complete
            self.selection_window.on_selection_cancelled = self._on_selection_cancelled
            self.selection_window.show()
            
        except Exception as e:
            self.logger.error(f"Error starting capture: {e}")
            messagebox.showerror("Error", f"Failed to start capture: {str(e)}")
    
    def _on_selection_complete(self, area: tuple, scale_factor: float = None) -> None:
        """Handle completed area selection."""
        self.logger.info(f"Selection complete: {area}")
        self.capture_area = area
        
        # Salva il scale factor
        if scale_factor:
            self._last_scale_factor = scale_factor
        
        # La selection window si distrugge da sola ora
        self.selection_window = None
        
        # Start capture immediatamente
        self._begin_capture()
    
    def _on_selection_cancelled(self) -> None:
        """Handle cancelled selection."""
        self.logger.info("Selection cancelled")
        
        # Clean up selection window
        if self.selection_window:
            self.selection_window.destroy()
            self.selection_window = None
        
        self.status_var.set("Selection cancelled")
    
    def _begin_capture(self) -> None:
        """Begin the actual capture process."""
        try:
            # Verify OCR is available
            if not self.ocr_processor.is_tesseract_available():
                messagebox.showerror(
                    "Tesseract Error",
                    "Tesseract OCR is not available. Please install it first."
                )
                self.start_button.config(state=tk.NORMAL)
                return
            
            scale_factor = getattr(self, '_last_scale_factor', 1.0)
            self.capture_window = CaptureWindow(
                self.root,
                self.capture_area,
                scale_factor
            )
            self.capture_window.on_stop = self._stop_capture
            self.capture_window.on_position_changed = self._on_capture_window_moved
            self.capture_window.show()
            
            # Get language code
            lang_code = self._get_language_code()
            if not lang_code:
                # Use English as fallback
                lang_code = "eng"
            
            # The capture area will be adjusted by the CaptureWindow itself
            # to account for the control frame positioned above it
            self.screen_capture.set_capture_area(self.capture_area)
            
            # Start capture
            if self.screen_capture.start_capture(lang_code, self.use_caption_mode.get()):
                self.is_capturing = True
                self.status_var.set("Capturing... (Press Ctrl+Q or STOP to stop)")
                # Show initial interval in status bar
                self._on_interval_change(self.capture_config.current_interval)
                # Change button to STOP
                self.start_button.config(
                    text="STOP",
                    bg="#f44336",
                    activebackground="#da190b"
                )
            else:
                messagebox.showerror("Error", "Failed to start capture")
                self._cleanup_capture()
                
        except Exception as e:
            self.logger.error(f"Error beginning capture: {e}")
            messagebox.showerror("Error", f"Failed to begin capture: {str(e)}")
            self._cleanup_capture()
    
    def _stop_capture(self) -> None:
        """Stop capture process."""
        try:
            self.logger.info("Stopping capture")
            
            # Stop screen capture
            output_file = self.screen_capture.stop_capture()
            
            # Clean up capture window
            if self.capture_window:
                self.capture_window.destroy()
                self.capture_window = None
            
            # Process the file if it exists
            if output_file:
                self._process_capture_file(output_file)
            else:
                self.status_var.set("Capture stopped")
            
            # Reset state
            self._cleanup_capture()
            
        except Exception as e:
            self.logger.error(f"Error stopping capture: {e}")
            self.status_var.set(f"Error: {str(e)}")
            self._cleanup_capture()
    
    def _process_capture_file(self, filepath: str) -> None:
        """Process the captured file."""
        try:
            # Skip Save As dialog during shutdown to avoid blocking
            if getattr(self, '_shutting_down', False):
                self.logger.info("Shutdown in progress, processing file without prompt")
                custom_name = None
            else:
                # Ask for custom name
                custom_name = simpledialog.askstring(
                    "Save As",
                    "Enter a name for the captured file:",
                    parent=self.root
                )

                # If user cancelled, don't process the file
                if custom_name is None:
                    self.status_var.set("Save cancelled")
                    return
            
            if custom_name:
                # Sanitize filename
                custom_name = re.sub(r'[^\w\-]', '_', custom_name)
            
            # Process the file
            processed_file = self.screen_capture.process_capture_file(filepath, custom_name)
            
            if processed_file:
                if custom_name:
                    self.status_var.set(f"Saved as: {custom_name}")
                else:
                    self.status_var.set("Capture processed and saved")
            else:
                self.status_var.set("Capture saved (no processing needed)")
                
        except Exception as e:
            self.logger.error(f"Error processing capture file: {e}")
            self.status_var.set("Capture saved (processing failed)")
    
    def _cleanup_capture(self) -> None:
        """Clean up after capture."""
        self.is_capturing = False
        self.capture_area = None
        self.interval_status_var.set("Interval: --")
        
        # Reset button to START
        self.start_button.config(
            text="START",
            bg="#4CAF50",
            activebackground="#45a049",
            state=tk.NORMAL
        )
        
        # Clear captured text display
        self.captured_text_display.config(
            text="Captured text will appear here",
            foreground='#888888'
        )
    
    def _on_capture_window_moved(self, new_area: tuple) -> None:
        """Handle capture window movement."""
        self.capture_area = new_area
        self.screen_capture.set_capture_area(new_area)
    
    def _on_text_captured(self, text: str) -> None:
        """Handle captured text."""
        # Update UI on main thread
        self.root.after(0, lambda: self._update_captured_text(text))
    
    def _update_captured_text(self, text: str) -> None:
        """Update captured text display."""
        display_text = self.text_processor.truncate_for_display(text)
        self.captured_text_display.config(
            text=display_text,
            foreground='black'
        )
    
    def _on_status_update(self, status: str) -> None:
        """Handle status update."""
        self.root.after(0, lambda: self.status_var.set(status))
    
    def _on_interval_change(self, interval: float) -> None:
        """Handle interval change."""
        self.root.after(0, lambda: self.interval_status_var.set(f"Interval: {interval:.1f}s"))
    
    def _on_document_mode_toggle(self) -> None:
        """Handle document mode toggle - invert logic for caption mode."""
        # Inverted logic: Document Mode checked = Caption Mode OFF
        self.use_caption_mode.set(not self.use_document_mode.get())
        
        mode = "Document Mode" if self.use_document_mode.get() else "Caption Mode"
        self.logger.info(f"OCR mode changed to: {mode}")
    
    def _get_language_code(self) -> Optional[str]:
        """Get the selected language code."""
        selected = self.selected_lang.get()
        
        for lang_name, lang_code in SUPPORTED_LANGUAGES:
            if lang_name == selected:
                # Check if language is available
                if self.ocr_processor.check_language_available(lang_code):
                    return lang_code
                
                # Language not available, ask to download
                if messagebox.askyesno(
                    "Missing Language",
                    f"Language '{selected}' is not available.\n"
                    "Would you like to download it?"
                ):
                    if self._download_language(lang_code):
                        return lang_code
                    else:
                        # Download failed, return None to reset dropdown
                        messagebox.showinfo(
                            "Language Not Available",
                            f"Failed to download '{selected}'. Using English instead."
                        )
                        return None
                else:
                    # User cancelled download, return None to reset dropdown
                    messagebox.showinfo(
                        "Language Not Available",
                        f"'{selected}' is not available. Using English instead."
                    )
                    return None
        
        # Default to English
        return "eng"
    
    def _download_language(self, lang_code: str) -> bool:
        """Download a language file."""
        dialog = LanguageDownloadDialog(self.root, self.language_manager)
        return dialog.download_language(lang_code)
    
    def _on_language_changed(self, event=None) -> None:
        """Handle language selection change."""
        selected = self.selected_lang.get()
        lang_code = self._get_language_code()
        
        if lang_code:
            self.settings.language = selected
        else:
            # If no language code returned (download cancelled/failed), revert to English
            self.selected_lang.set("English")
            self.settings.language = "English"
    
    def _toggle_debug(self) -> None:
        """Toggle debug mode."""
        self.settings.debug_enabled = self.debug_enabled.get()
        self.settings.apply_debug_mode()
    
    def _configure_interval(self) -> None:
        """Open interval configuration dialog."""
        dialog = IntervalConfigDialog(self.root, self.capture_config)
        dialog.show()

        # Update interval display after dialog closes
        self.interval_status_var.set(f"Interval: {self.capture_config.min_capture_interval:.1f}s")

    def _configure_post_processing(self) -> None:
        """Open post-processing configuration dialog."""
        dialog = PostProcessConfigDialog(self.root, self.capture_config, self.settings)
        dialog.show()

    def _save_settings(self) -> None:
        """Save current settings."""
        profile_name = simpledialog.askstring(
            "Save Settings",
            "Enter a name for this settings profile:",
            parent=self.root
        )
        
        if profile_name:
            # Update settings object
            self.settings.language = self.selected_lang.get()
            self.settings.debug_enabled = self.debug_enabled.get()
            self.settings.use_caption_mode = self.use_caption_mode.get()
            
            # Save
            if self.settings.save(profile_name):
                messagebox.showinfo(
                    "Settings Saved",
                    f"Settings saved as '{profile_name}'"
                )
            else:
                messagebox.showerror(
                    "Error",
                    "Failed to save settings"
                )
    
    def _load_settings_dialog(self) -> None:
        """Open settings loading dialog."""
        dialog = SettingsDialog(self.root, self.settings)
        if dialog.show():
            # Apply loaded settings
            self.selected_lang.set(self.settings.language)
            self.debug_enabled.set(self.settings.debug_enabled)
            self.use_caption_mode.set(self.settings.use_caption_mode)
            self.use_document_mode.set(not self.settings.use_caption_mode)
            self.text_processor.similarity_threshold = self.settings.text_similarity_threshold
            self.settings.apply_debug_mode()

            # Update capture configuration and sync intervals
            self.capture_config = self.settings.capture_config
            self.screen_capture.capture_config = self.capture_config
            
            # Update interval status display immediately
            self.interval_status_var.set(f"Interval: {self.capture_config.min_capture_interval:.1f}s")
    
    def _open_captures_folder(self) -> None:
        """Open captures folder."""
        try:
            self.file_manager.open_directory(self.file_manager.CAPTURES_DIR)
            self.status_var.set("Opened captures folder")
        except Exception as e:
            self.logger.error(f"Error opening captures folder: {e}")
            messagebox.showerror("Error", f"Failed to open captures folder: {str(e)}")
    
    def _open_log_folder(self) -> None:
        """Open logs folder."""
        try:
            self.file_manager.open_directory(self.file_manager.LOGS_DIR)
            self.status_var.set("Opened logs folder")
        except Exception as e:
            self.logger.error(f"Error opening logs folder: {e}")
            messagebox.showerror("Error", f"Failed to open logs folder: {str(e)}")
    
    def _show_about(self):
        """Show About dialog with information from version.txt."""
        about_text = f"""{app_info.app_name}
Version {app_info.version_string}

A tool for real-time capture and transcription of captions 
and subtitles from video conferencing applications.

Developed by: {app_info.author}
Website: {app_info.url}

© {datetime.now().year} - OCR caption capture solution"""
        
        messagebox.showinfo(f"About {app_info.app_name}", about_text)
    
    def _show_instructions(self) -> None:
        """Show instructions dialog with formatted content."""
        # Create custom dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("CaptiOCR \u2014 Instructions")
        dialog.transient(self.root)
        dialog.grab_set()

        # Set size and center
        width, height = 560, 620
        x = (dialog.winfo_screenwidth() - width) // 2
        y = (dialog.winfo_screenheight() - height) // 2
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        dialog.minsize(480, 500)

        # Main frame
        frame = ttk.Frame(dialog, padding="16")
        frame.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(
            frame,
            wrap=tk.WORD,
            width=60,
            height=30,
            font=("Segoe UI", 10),
            padx=12,
            pady=8,
            spacing1=2,
            spacing3=2,
            borderwidth=0,
            highlightthickness=0,
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(frame, command=text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.config(yscrollcommand=scrollbar.set)

        # Configure text tags for formatting
        text_widget.tag_configure("heading", font=("Segoe UI", 13, "bold"), spacing1=10, spacing3=4)
        text_widget.tag_configure("section", font=("Segoe UI", 11, "bold"), spacing1=12, spacing3=2)
        text_widget.tag_configure("body", font=("Segoe UI", 10), spacing1=1, spacing3=1)
        text_widget.tag_configure("shortcut", font=("Consolas", 10), foreground="#0066CC")
        text_widget.tag_configure("tip", font=("Segoe UI", 10, "italic"), foreground="#666666")

        # Insert formatted content
        text_widget.insert(tk.END, "CaptiOCR Instructions\n", "heading")

        text_widget.insert(tk.END, "\nGetting Started\n", "section")
        text_widget.insert(tk.END, (
            "1.  Select the OCR language from the dropdown menu.\n"
            "2.  Click 'Start' to begin a capture session.\n"
            "3.  Draw a selection rectangle around the caption area\n"
            "     by clicking and dragging on screen.\n"
            "4.  Press Enter to confirm. OCR capture starts immediately.\n"
        ), "body")

        text_widget.insert(tk.END, "\nDuring Capture\n", "section")
        text_widget.insert(tk.END, (
            "5.  The yellow capture window shows the active area.\n"
            "     You can drag it to follow moving captions.\n"
            "6.  Text is captured every 3\u20134 seconds (configurable).\n"
            "7.  A raw capture file is saved automatically in the\n"
            "     captures/ folder with full OCR content.\n"
        ), "body")

        text_widget.insert(tk.END, "\nStopping & Post-Processing\n", "section")
        text_widget.insert(tk.END, (
            "8.  Press the Stop button or Ctrl+Q to end capture.\n"
            "9.  After stopping, a processed file is generated with\n"
            "     deduplication, speaker labels, and cleaned text.\n"
            "10. Open your files via File \u2192 Open Captures Folder.\n"
        ), "body")

        text_widget.insert(tk.END, "\nKeyboard Shortcuts\n", "section")
        text_widget.insert(tk.END, "  Ctrl+Q", "shortcut")
        text_widget.insert(tk.END, "      Stop capture\n", "body")
        text_widget.insert(tk.END, "  Enter", "shortcut")
        text_widget.insert(tk.END, "        Confirm selection area\n", "body")
        text_widget.insert(tk.END, "  Escape", "shortcut")
        text_widget.insert(tk.END, "       Cancel selection\n", "body")

        text_widget.insert(tk.END, "\nSettings\n", "section")
        text_widget.insert(tk.END, (
            "  \u2022  Settings \u2192 Configure Capture Interval\n"
            "     Adjust min/max polling interval (default: 3\u20134s).\n"
            "  \u2022  Settings \u2192 Configure Sensitivity\n"
            "     Tune similarity threshold and delta parameters.\n"
            "  \u2022  Settings \u2192 Configure Post-Processing\n"
            "     Adjust dedup thresholds for the processed file.\n"
        ), "body")

        text_widget.insert(tk.END, "\nTips\n", "section")
        text_widget.insert(tk.END, (
            "  \u2022  Place the selection box tightly around the subtitle\n"
            "     area for best OCR accuracy.\n"
            "  \u2022  Use Caption Mode (enabled by default) for subtitle-\n"
            "     optimized OCR settings.\n"
            "  \u2022  The raw file is a faithful OCR log \u2014 it is never\n"
            "     modified after capture. Post-processing creates a\n"
            "     separate clean file that can always be regenerated.\n"
        ), "tip")

        text_widget.config(state=tk.DISABLED)

        ttk.Button(
            dialog,
            text="Close",
            command=dialog.destroy
        ).pack(pady=(4, 12))
    
    def on_closing(self) -> None:
        """Handle window closing."""
        self.logger.info("Application closing")
        self._shutting_down = True

        try:
            # Stop any active capture (skip Save As dialog during shutdown)
            if self.is_capturing:
                self._stop_capture()

            # Clean up global hotkeys
            try:
                keyboard.unhook_all()
                self.logger.info("Global hotkeys cleaned up")
            except Exception as e:
                self.logger.warning(f"Error cleaning up hotkeys: {e}")

            # Save current settings as last configuration
            self.settings.save_last_config()

            # Destroy windows
            if self.selection_window:
                self.selection_window.destroy()
            if self.capture_window:
                self.capture_window.destroy()

            # Destroy main window
            self.root.destroy()

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            self.root.destroy()
    
    def run(self) -> None:
        """Run the application."""
        self.logger.info("Starting main event loop")
        self.root.mainloop()