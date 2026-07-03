"""
Dialog windows for various settings and configurations.
"""
import tkinter as tk
from tkinter import ttk, messagebox

from .base_window import BaseWindow
from .dialog_base import DialogBase
from ..config.settings import Settings
from ..models.capture_config import CaptureConfig
from ..utils.language_manager import LanguageManager
from ..config.constants import TESSDATA_DIR


class SettingsDialog(DialogBase):
    """Dialog for loading settings profiles."""
    
    def __init__(self, parent: tk.Tk, settings: Settings):
        """Initialize settings dialog."""
        super().__init__(parent, "Load Settings", 450, 350)
        self.settings = settings
        self.selected_profile = None
        self.profiles = []
    
    def show(self) -> bool:
        """
        Show the dialog and wait for user selection.
        
        Returns:
            True if settings were loaded, False otherwise
        """
        # Get available profiles
        self.profiles = self.settings.list_profiles()
        
        if not self.profiles:
            messagebox.showinfo("No Settings", "No saved settings profiles found.")
            return False
        
        # Create dialog using base class
        self.create_dialog()
        
        # Create main frame and title
        frame = self.create_main_frame()
        self.create_title_label(frame, "Load Settings Profile")
        
        ttk.Label(frame, text="Choose a settings profile to load:").pack(pady=(0, 10))
        
        # Create listbox with scrollbar
        listbox_frame = ttk.Frame(frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.listbox = tk.Listbox(listbox_frame, width=50, height=10)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # Add profiles
        for i, profile in enumerate(self.profiles):
            display_text = f"{profile['name']} ({profile['saved_date']})"
            self.listbox.insert(i, display_text)
        
        # Select first item
        if self.profiles:
            self.listbox.selection_set(0)
        
        # Buttons using base class
        button_frame = self.create_button_frame(frame)
        self.add_ok_cancel_buttons(
            button_frame, 
            ok_text="Load Selected", 
            ok_callback=self._on_load,
            ok_width=12
        )
        
        # Wait for window to close
        self.parent.wait_window(self.dialog)
        
        # Return whether profile was loaded
        return self.selected_profile is not None
    
    def _on_load(self) -> None:
        """Handle load button click."""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a profile to load.")
            return
            
        # Get selected profile
        profile = self.profiles[selection[0]]
        
        try:
            # Load the profile
            if self.settings.load(profile['name']):
                self.selected_profile = profile['name']
                
                # Show success message
                messagebox.showinfo(
                    "Settings Loaded",
                    f"Profile '{profile['name']}' loaded successfully.\n\n"
                    f"Language: {self.settings.language}\n"
                    f"Debug: {'Enabled' if self.settings.debug_enabled else 'Disabled'}\n"
                    f"Caption Mode: {'Enabled' if self.settings.use_caption_mode else 'Disabled'}\n"
                    f"Min Interval: {self.settings.capture_config.min_capture_interval:.1f}s\n"
                    f"Max Interval: {self.settings.capture_config.max_capture_interval:.1f}s"
                )
                
                # Close dialog using base class method
                self.close_dialog()
            else:
                messagebox.showerror(
                    "Load Error",
                    f"Failed to load profile '{profile['name']}'.\n"
                    f"The profile file may be corrupted or missing."
                )
        except Exception as e:
            messagebox.showerror(
                "Load Error", 
                f"Error loading profile '{profile['name']}':\n{str(e)}"
            )


class LanguageDownloadDialog(BaseWindow):
    """Dialog for downloading language files."""
    
    def __init__(self, parent: tk.Tk, language_manager: LanguageManager):
        """Initialize language download dialog."""
        super().__init__(parent, "Download Language")
        self.language_manager = language_manager
        self.download_success = False
    
    def download_language(self, lang_code: str) -> bool:
        """
        Download a language file with progress indication.
        
        Args:
            lang_code: Language code to download
            
        Returns:
            True if download successful
        """
        # Create window
        self.create_window()
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # Set size and center
        self.center_window(400, 150)
        
        # Create content
        self.main_frame = ttk.Frame(self.window, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.status_label = ttk.Label(
            self.main_frame,
            text=f"Downloading {lang_code} language file..."
        )
        self.status_label.pack(pady=10)
        
        self.progress_bar = ttk.Progressbar(
            self.main_frame,
            mode='indeterminate',
            length=350
        )
        self.progress_bar.pack(pady=10)
        self.progress_bar.start()
        
        # Start download after window is shown
        self.window.after(100, lambda: self._do_download(lang_code))
        
        # Wait for window to close
        self.parent.wait_window(self.window)
        
        return self.download_success
    
    def _do_download(self, lang_code: str) -> None:
        """Perform the actual download in a background thread."""
        import threading

        def _safe_after(callback):
            """Schedule callback on main thread only if window still exists."""
            try:
                if self._window_exists():
                    self.window.after(0, callback)
            except Exception:
                pass

        def progress_callback(message: str):
            _safe_after(lambda: self.status_label.config(text=message))

        def download_thread():
            """Background thread for downloading."""
            try:
                # Download the language
                success = self.language_manager.download_language(
                    lang_code,
                    TESSDATA_DIR,
                    progress_callback
                )

                # Schedule completion handling on main thread
                _safe_after(lambda: self._on_download_complete(success, lang_code))

            except Exception as e:
                # Schedule error handling on main thread
                err_msg = str(e)
                _safe_after(lambda: self._on_download_error(err_msg, lang_code))

        # Start download in background thread
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()

    def _on_download_complete(self, success: bool, lang_code: str) -> None:
        """Handle download completion on main thread."""
        if success:
            self.download_success = True
            self.status_label.config(text="Download complete!")
            self.progress_bar.stop()

            # Close after delay
            self.parent.after(2000, self.window.destroy)
        else:
            self._on_download_error("Download failed", lang_code)

    def _on_download_error(self, error_msg: str, lang_code: str) -> None:
        """Handle download error on main thread."""
        self.progress_bar.stop()
        messagebox.showerror(
            "Download Failed",
            f"Failed to download {lang_code} language file: {error_msg}"
        )
        # Always release grab before destroying
        try:
            if self.window and self._window_exists():
                self.window.grab_release()
                self.window.destroy()
        except Exception:
            pass
    

class IntervalConfigDialog(DialogBase):
    """Dialog for configuring capture intervals."""
    
    def __init__(self, parent: tk.Tk, capture_config: CaptureConfig):
        """Initialize interval configuration dialog."""
        super().__init__(parent, "Configure Capture Interval", 400, 300)
        self.capture_config = capture_config
    
    def show(self) -> None:
        """Show the configuration dialog."""
        # Create dialog using base class
        self.create_dialog()
        
        # Create main frame and title
        frame = self.create_main_frame()
        self.create_title_label(frame, "Configure Capture Intervals")
        
        # Minimum interval
        min_frame = ttk.Frame(frame)
        min_frame.pack(fill=tk.X, pady=5)
        ttk.Label(min_frame, text="Minimum interval (seconds):").pack(side=tk.LEFT)
        self.min_var = tk.DoubleVar(value=self.capture_config.min_capture_interval)
        ttk.Spinbox(
            min_frame,
            from_=0.5,
            to=5,
            increment=0.5,
            textvariable=self.min_var,
            width=8
        ).pack(side=tk.RIGHT)
        
        # Maximum interval
        max_frame = ttk.Frame(frame)
        max_frame.pack(fill=tk.X, pady=5)
        ttk.Label(max_frame, text="Maximum interval (seconds):").pack(side=tk.LEFT)
        self.max_var = tk.DoubleVar(value=self.capture_config.max_capture_interval)
        ttk.Spinbox(
            max_frame,
            from_=1,
            to=8,
            increment=0.5,
            textvariable=self.max_var,
            width=8
        ).pack(side=tk.RIGHT)
        
        # Sensitivity
        sens_frame = ttk.Frame(frame)
        sens_frame.pack(fill=tk.X, pady=5)
        ttk.Label(sens_frame, text="Increase after (captures):").pack(side=tk.LEFT)
        self.sensitivity_var = tk.IntVar(value=self.capture_config.max_similar_captures)
        ttk.Spinbox(
            sens_frame,
            from_=1,
            to=5,
            increment=1,
            textvariable=self.sensitivity_var,
            width=8
        ).pack(side=tk.RIGHT)
        
        # Info
        ttk.Label(
            frame,
            text=(
                "Recall-first: lower intervals capture more text.\n"
                "Recommended: Min 3.0s, Max 4.0s for best coverage.\n"
                "Higher values save resources but may miss brief speech."
            ),
            font=("Arial", 9),
            foreground="gray",
            justify=tk.CENTER
        ).pack(pady=15)
        
        # Buttons using base class
        btn_frame = self.create_button_frame(frame)
        self.add_ok_cancel_buttons(btn_frame, ok_callback=self._on_save)
    
    def _on_save(self) -> None:
        """Handle save button click."""
        try:
            # Get values
            new_min = float(self.min_var.get())
            new_max = float(self.max_var.get())
            new_sensitivity = int(self.sensitivity_var.get())
            
            # Validate values
            if new_min >= new_max:
                messagebox.showerror("Invalid Values", "Minimum interval must be less than maximum interval")
                return
            
            # Update configuration
            self.capture_config.set_intervals(new_min, new_max)
            self.capture_config.set_max_similar_captures(new_sensitivity)
            
            # Show confirmation
            messagebox.showinfo(
                "Settings Updated",
                f"Intervals updated:\nMin: {new_min}s, Max: {new_max}s\nSensitivity: {new_sensitivity}"
            )
            
            # Close the dialog using base class method
            self.close_dialog()
            
        except ValueError as e:
            messagebox.showerror("Invalid Values", f"Please enter valid numbers: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")


class PostProcessConfigDialog(DialogBase):
    """Dialog for configuring the recall-first post-processing pipeline."""

    def __init__(self, parent: tk.Tk, capture_config: CaptureConfig, settings=None):
        super().__init__(parent, "Configure Post-Processing", 550, 720)
        self.capture_config = capture_config
        self.settings = settings

    def show(self) -> None:
        """Show the post-processing configuration dialog."""
        self.create_dialog()
        frame = self.create_main_frame()
        self.create_title_label(frame, "Configure Post-Processing")

        ttk.Label(
            frame,
            text="Adjust how processed files deduplicate and filter captured text.",
            font=("Arial", 9), foreground="gray"
        ).pack(pady=(0, 15))

        # --- Emit Score Threshold ---
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=6)
        ttk.Label(row1, text="Emit Score Threshold:", width=22, anchor='w').pack(side=tk.LEFT)
        self.emit_score_var = tk.IntVar(
            value=int(self.capture_config.post_process_emit_score_threshold * 10))
        ttk.Spinbox(row1, from_=5, to=50, increment=5,
                    textvariable=self.emit_score_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="× 0.1 (e.g. 20 = 2.0)", font=("Arial", 8),
                  foreground="gray").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            frame,
            text="   Minimum novelty score to emit a frame. Lower = keep more, Higher = stricter.",
            font=("Arial", 8), foreground="#555", justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 6))

        # --- Frequency Window ---
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=6)
        ttk.Label(row2, text="Frequency Window:", width=22, anchor='w').pack(side=tk.LEFT)
        self.freq_window_var = tk.IntVar(
            value=self.capture_config.post_process_freq_window_size)
        ttk.Spinbox(row2, from_=10, to=60, increment=5,
                    textvariable=self.freq_window_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="recent frames for IDF", font=("Arial", 8),
                  foreground="gray").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            frame,
            text="   Frames tracked to score word rarity. Longer = slower adaptation.",
            font=("Arial", 8), foreground="#555", justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 6))

        # --- Frame Voting Window ---
        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=6)
        ttk.Label(row3, text="Frame Voting Window:", width=22, anchor='w').pack(side=tk.LEFT)
        self.frame_window_var = tk.IntVar(
            value=self.capture_config.post_process_frame_window)
        ttk.Spinbox(row3, from_=2, to=5, increment=1,
                    textvariable=self.frame_window_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row3, text="consecutive frames", font=("Arial", 8),
                  foreground="gray").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            frame,
            text="   ROVER votes new tokens across this many frames for temporal confirmation.",
            font=("Arial", 8), foreground="#555", justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 6))

        # --- Min Sentence Words ---
        row4 = ttk.Frame(frame)
        row4.pack(fill=tk.X, pady=6)
        ttk.Label(row4, text="Min Sentence Words:", width=22, anchor='w').pack(side=tk.LEFT)
        self.min_words_var = tk.IntVar(
            value=self.capture_config.post_process_min_sentence_words)
        ttk.Spinbox(row4, from_=1, to=5, increment=1,
                    textvariable=self.min_words_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row4, text="words minimum", font=("Arial", 8),
                  foreground="gray").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            frame,
            text="   Lower = keeps short replies (Sure, Yes). Higher = cleaner output.",
            font=("Arial", 8), foreground="#555", justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 6))

        # --- Separator and tip ---
        ttk.Separator(frame, orient='horizontal').pack(fill=tk.X, pady=10)
        ttk.Label(
            frame,
            text="Tip: These settings affect only post-processing of saved capture files.\n"
                 "They do not change live capture behavior.",
            font=("Arial", 9), foreground="#0066cc", justify=tk.CENTER
        ).pack(pady=8)

        # --- Buttons ---
        btn_frame = self.create_button_frame(frame)
        ttk.Button(btn_frame, text="Reset to Defaults",
                   command=self._on_reset).pack(side=tk.LEFT, padx=5)
        ttk.Frame(btn_frame).pack(side=tk.LEFT, expand=True)
        self.add_ok_cancel_buttons(btn_frame, ok_text="Save",
                                   ok_callback=self._on_save, ok_width=12)

    def _on_reset(self) -> None:
        """Reset all values to defaults."""
        from ..config.constants import (
            POST_PROCESS_EMIT_SCORE_THRESHOLD,
            POST_PROCESS_FREQ_WINDOW_SIZE,
            POST_PROCESS_FRAME_CONSENSUS_WINDOW,
            POST_PROCESS_MIN_SENTENCE_WORDS
        )
        self.emit_score_var.set(int(POST_PROCESS_EMIT_SCORE_THRESHOLD * 10))
        self.freq_window_var.set(POST_PROCESS_FREQ_WINDOW_SIZE)
        self.frame_window_var.set(POST_PROCESS_FRAME_CONSENSUS_WINDOW)
        self.min_words_var.set(POST_PROCESS_MIN_SENTENCE_WORDS)
        messagebox.showinfo(
            "Reset to Defaults",
            "All values have been reset to default settings.\n"
            "Click Save to apply these changes."
        )

    def _on_save(self) -> None:
        """Validate and save post-processing settings."""
        try:
            self.dialog.update_idletasks()

            new_emit_score = float(self.emit_score_var.get()) / 10.0
            new_freq_window = int(self.freq_window_var.get())
            new_frame_window = int(self.frame_window_var.get())
            new_min_words = int(self.min_words_var.get())

            # Validate ranges
            if not (0.5 <= new_emit_score <= 5.0):
                messagebox.showerror("Invalid Value",
                                     "Emit Score Threshold must be between 0.5 and 5.0.")
                return
            if not (10 <= new_freq_window <= 60):
                messagebox.showerror("Invalid Value",
                                     "Frequency Window must be between 10 and 60 frames.")
                return
            if not (2 <= new_frame_window <= 5):
                messagebox.showerror("Invalid Value",
                                     "Frame Voting Window must be between 2 and 5.")
                return
            if not (1 <= new_min_words <= 5):
                messagebox.showerror("Invalid Value",
                                     "Min Sentence Words must be between 1 and 5.")
                return

            # Apply to config
            self.capture_config.post_process_emit_score_threshold = new_emit_score
            self.capture_config.post_process_freq_window_size = new_freq_window
            self.capture_config.post_process_frame_window = new_frame_window
            self.capture_config.post_process_min_sentence_words = new_min_words

            # Persist
            save_success = False
            if self.settings:
                save_success = self.settings.save_last_config()
                if not save_success:
                    messagebox.showerror(
                        "Save Error",
                        "Failed to save settings to disk.\n"
                        "Settings will be applied for this session only."
                    )

            save_msg = "Settings saved to disk." if save_success else "Settings applied (not saved to disk)."
            messagebox.showinfo(
                "Settings Updated",
                f"Post-processing updated:\n"
                f"Emit Score Threshold: {new_emit_score:.1f}\n"
                f"Frequency Window: {new_freq_window} frames\n"
                f"Frame Voting Window: {new_frame_window}\n"
                f"Min Sentence Words: {new_min_words}\n\n"
                f"{save_msg}"
            )

            self.close_dialog()

        except ValueError as e:
            messagebox.showerror("Invalid Values", f"Please enter valid numbers: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")