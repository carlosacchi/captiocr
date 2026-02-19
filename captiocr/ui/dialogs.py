"""
Dialog windows for various settings and configurations.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

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
                _safe_after(lambda: self._on_download_error(str(e), lang_code))

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
            to=10,
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
            text="Lower values = more responsive but use more resources\nHigher values = save resources but may miss brief text",
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


class SensitivityConfigDialog(DialogBase):
    """Dialog for configuring delta extraction sensitivity."""

    def __init__(self, parent: tk.Tk, capture_config: CaptureConfig, settings=None):
        """Initialize sensitivity configuration dialog."""
        super().__init__(parent, "Configure Capture Sensitivity", 550, 650)
        self.capture_config = capture_config
        self.settings = settings

    def show(self) -> None:
        """Show the configuration dialog."""
        # Create dialog using base class
        self.create_dialog()

        # Create main frame and title
        frame = self.create_main_frame()
        self.create_title_label(frame, "Configure Capture Sensitivity")

        ttk.Label(
            frame,
            text="Adjust how the application detects and filters duplicate content",
            font=("Arial", 9),
            foreground="gray"
        ).pack(pady=(0, 15))

        # Minimum Delta Words
        min_delta_frame = ttk.Frame(frame)
        min_delta_frame.pack(fill=tk.X, pady=8)
        ttk.Label(min_delta_frame, text="Minimum Delta Words:", width=22, anchor='w').pack(side=tk.LEFT)
        self.min_delta_var = tk.IntVar(value=self.capture_config.min_delta_words)
        ttk.Spinbox(
            min_delta_frame,
            from_=2,
            to=10,
            increment=1,
            textvariable=self.min_delta_var,
            width=10
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            min_delta_frame,
            text="⓵ Min words for new content",
            font=("Arial", 8),
            foreground="gray"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            frame,
            text="   Lower = captures smaller fragments\n   Higher = filters out small changes",
            font=("Arial", 8),
            foreground="#555",
            justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 10))

        # Recent Texts Window Size
        window_frame = ttk.Frame(frame)
        window_frame.pack(fill=tk.X, pady=8)
        ttk.Label(window_frame, text="Comparison Window:", width=22, anchor='w').pack(side=tk.LEFT)
        self.window_var = tk.IntVar(value=self.capture_config.recent_texts_window_size)
        ttk.Spinbox(
            window_frame,
            from_=3,
            to=10,
            increment=1,
            textvariable=self.window_var,
            width=10
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            window_frame,
            text="⓶ Previous captures to check",
            font=("Arial", 8),
            foreground="gray"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            frame,
            text="   Lower = faster, may miss patterns\n   Higher = better redundancy detection",
            font=("Arial", 8),
            foreground="#555",
            justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 10))

        # Delta Buffer Threshold
        buffer_frame = ttk.Frame(frame)
        buffer_frame.pack(fill=tk.X, pady=8)
        ttk.Label(buffer_frame, text="Buffer Flush Threshold:", width=22, anchor='w').pack(side=tk.LEFT)
        self.buffer_var = tk.IntVar(value=self.capture_config.delta_buffer_threshold)
        ttk.Spinbox(
            buffer_frame,
            from_=2,
            to=5,
            increment=1,
            textvariable=self.buffer_var,
            width=10
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            buffer_frame,
            text="⓷ Fragments before saving",
            font=("Arial", 8),
            foreground="gray"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            frame,
            text="   Lower = more frequent saves\n   Higher = waits to combine fragments",
            font=("Arial", 8),
            foreground="#555",
            justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 10))

        # Incremental Threshold
        threshold_frame = ttk.Frame(frame)
        threshold_frame.pack(fill=tk.X, pady=8)
        ttk.Label(threshold_frame, text="Incremental Detection:", width=22, anchor='w').pack(side=tk.LEFT)
        self.threshold_var = tk.IntVar(value=int(self.capture_config.incremental_threshold * 100))
        ttk.Spinbox(
            threshold_frame,
            from_=50,
            to=90,
            increment=5,
            textvariable=self.threshold_var,
            width=10
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(
            threshold_frame,
            text="⓸ % overlap for subtitles",
            font=("Arial", 8),
            foreground="gray"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            frame,
            text="   Lower = more sensitive to changes\n   Higher = stricter incremental detection",
            font=("Arial", 8),
            foreground="#555",
            justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 10))

        # Separator
        ttk.Separator(frame, orient='horizontal').pack(fill=tk.X, pady=15)

        # Info
        ttk.Label(
            frame,
            text="💡 Tip: Start with defaults. Adjust if you see too many fragments or duplicates.",
            font=("Arial", 9),
            foreground="#0066cc",
            justify=tk.CENTER
        ).pack(pady=10)

        # Buttons using base class
        btn_frame = self.create_button_frame(frame)

        # Add Reset to Defaults button on the left
        ttk.Button(
            btn_frame,
            text="Reset to Defaults",
            command=self._on_reset
        ).pack(side=tk.LEFT, padx=5)

        # Add spacer to push Save/Cancel to the right
        ttk.Frame(btn_frame).pack(side=tk.LEFT, expand=True)

        self.add_ok_cancel_buttons(
            btn_frame,
            ok_text="Save",
            ok_callback=self._on_save,
            ok_width=12
        )

    def _on_reset(self) -> None:
        """Reset all values to defaults."""
        from ..config.constants import (
            DEFAULT_MIN_DELTA_WORDS,
            DEFAULT_RECENT_TEXTS_WINDOW_SIZE,
            DEFAULT_DELTA_BUFFER_THRESHOLD,
            DEFAULT_INCREMENTAL_THRESHOLD
        )

        self.min_delta_var.set(DEFAULT_MIN_DELTA_WORDS)
        self.window_var.set(DEFAULT_RECENT_TEXTS_WINDOW_SIZE)
        self.buffer_var.set(DEFAULT_DELTA_BUFFER_THRESHOLD)
        self.threshold_var.set(int(DEFAULT_INCREMENTAL_THRESHOLD * 100))

        messagebox.showinfo(
            "Reset to Defaults",
            "All values have been reset to default settings.\n"
            "Click Save to apply these changes."
        )

    def _on_save(self) -> None:
        """Handle save button click."""
        try:
            # Force update of all spinbox values to ensure they're captured
            self.dialog.update_idletasks()

            # Get values
            new_min_delta = int(self.min_delta_var.get())
            new_window = int(self.window_var.get())
            new_buffer = int(self.buffer_var.get())
            new_threshold = float(self.threshold_var.get()) / 100.0

            # Validate values
            if new_min_delta < 2 or new_min_delta > 10:
                messagebox.showerror("Invalid Value", "Minimum delta words must be between 2 and 10")
                return
            if new_window < 3 or new_window > 10:
                messagebox.showerror("Invalid Value", "Comparison window must be between 3 and 10")
                return
            if new_buffer < 2 or new_buffer > 5:
                messagebox.showerror("Invalid Value", "Buffer threshold must be between 2 and 5")
                return
            if new_threshold < 0.5 or new_threshold > 0.9:
                messagebox.showerror("Invalid Value", "Incremental threshold must be between 50% and 90%")
                return

            # Update configuration
            self.capture_config.min_delta_words = new_min_delta
            self.capture_config.recent_texts_window_size = new_window
            self.capture_config.delta_buffer_threshold = new_buffer
            self.capture_config.incremental_threshold = new_threshold

            # Save settings to persist changes
            save_success = False
            if self.settings:
                save_success = self.settings.save_last_config()
                if not save_success:
                    messagebox.showerror(
                        "Save Error",
                        "Failed to save settings to disk.\n"
                        "Settings will be applied for this session only."
                    )

            # Show confirmation
            save_msg = "Settings saved to disk." if save_success else "Settings applied (not saved to disk)."
            messagebox.showinfo(
                "Settings Updated",
                f"Sensitivity updated:\n"
                f"Min Delta Words: {new_min_delta}\n"
                f"Comparison Window: {new_window}\n"
                f"Buffer Threshold: {new_buffer}\n"
                f"Incremental Detection: {int(new_threshold * 100)}%\n\n"
                f"{save_msg}"
            )

            # Close the dialog using base class method
            self.close_dialog()

        except ValueError as e:
            messagebox.showerror("Invalid Values", f"Please enter valid numbers: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")


class PostProcessConfigDialog(DialogBase):
    """Dialog for configuring post-processing deduplication parameters."""

    def __init__(self, parent: tk.Tk, capture_config: CaptureConfig, settings=None):
        super().__init__(parent, "Configure Post-Processing", 550, 680)
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

        # --- Sentence Similarity ---
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=8)
        ttk.Label(row1, text="Sentence Similarity:", width=22, anchor='w').pack(side=tk.LEFT)
        self.similarity_var = tk.IntVar(
            value=int(self.capture_config.post_process_sentence_similarity * 100))
        ttk.Spinbox(row1, from_=50, to=95, increment=5,
                    textvariable=self.similarity_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="% fuzzy match", font=("Arial", 8),
                  foreground="gray").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            frame,
            text="   Lower = more aggressive duplicate removal, may drop valid variations\n"
                 "   Higher = keeps more sentence variations, less deduplication",
            font=("Arial", 8), foreground="#555", justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 10))

        # --- Novelty Threshold ---
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=8)
        ttk.Label(row2, text="Novelty Threshold:", width=22, anchor='w').pack(side=tk.LEFT)
        self.novelty_var = tk.IntVar(
            value=int(self.capture_config.post_process_novelty_threshold * 100))
        ttk.Spinbox(row2, from_=5, to=50, increment=5,
                    textvariable=self.novelty_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="% new content words", font=("Arial", 8),
                  foreground="gray").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            frame,
            text="   Lower = keeps sentences even with few new words, more complete output\n"
                 "   Higher = requires more unique words per sentence, stricter filtering",
            font=("Arial", 8), foreground="#555", justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 10))

        # --- Min Sentence Words ---
        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=8)
        ttk.Label(row3, text="Min Sentence Words:", width=22, anchor='w').pack(side=tk.LEFT)
        self.min_words_var = tk.IntVar(
            value=self.capture_config.post_process_min_sentence_words)
        ttk.Spinbox(row3, from_=2, to=10, increment=1,
                    textvariable=self.min_words_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row3, text="words minimum", font=("Arial", 8),
                  foreground="gray").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            frame,
            text="   Lower = keeps short fragments (e.g. names, brief replies)\n"
                 "   Higher = filters out short fragments, cleaner but may lose context",
            font=("Arial", 8), foreground="#555", justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 10))

        # --- Global Window Size ---
        row4 = ttk.Frame(frame)
        row4.pack(fill=tk.X, pady=8)
        ttk.Label(row4, text="Global Window Size:", width=22, anchor='w').pack(side=tk.LEFT)
        self.window_var = tk.IntVar(
            value=self.capture_config.post_process_global_window_size)
        ttk.Spinbox(row4, from_=10, to=100, increment=10,
                    textvariable=self.window_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(row4, text="recent sentences", font=("Arial", 8),
                  foreground="gray").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            frame,
            text="   Lower = shorter memory, faster processing, may miss distant duplicates\n"
                 "   Higher = broader dedup scope, catches more repetitions across the file",
            font=("Arial", 8), foreground="#555", justify=tk.LEFT
        ).pack(anchor='w', pady=(0, 10))

        # --- Separator and tip ---
        ttk.Separator(frame, orient='horizontal').pack(fill=tk.X, pady=15)
        ttk.Label(
            frame,
            text="Tip: These settings affect only post-processing of saved capture files.\n"
                 "They do not change live capture behavior.",
            font=("Arial", 9), foreground="#0066cc", justify=tk.CENTER
        ).pack(pady=10)

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
            POST_PROCESS_SENTENCE_SIMILARITY,
            POST_PROCESS_NOVELTY_THRESHOLD,
            POST_PROCESS_MIN_SENTENCE_WORDS,
            POST_PROCESS_GLOBAL_WINDOW_SIZE
        )
        self.similarity_var.set(int(POST_PROCESS_SENTENCE_SIMILARITY * 100))
        self.novelty_var.set(int(POST_PROCESS_NOVELTY_THRESHOLD * 100))
        self.min_words_var.set(POST_PROCESS_MIN_SENTENCE_WORDS)
        self.window_var.set(POST_PROCESS_GLOBAL_WINDOW_SIZE)
        messagebox.showinfo(
            "Reset to Defaults",
            "All values have been reset to default settings.\n"
            "Click Save to apply these changes."
        )

    def _on_save(self) -> None:
        """Validate and save post-processing settings."""
        try:
            self.dialog.update_idletasks()

            new_similarity = float(self.similarity_var.get()) / 100.0
            new_novelty = float(self.novelty_var.get()) / 100.0
            new_min_words = int(self.min_words_var.get())
            new_window = int(self.window_var.get())

            # Validate ranges
            if not (0.50 <= new_similarity <= 0.95):
                messagebox.showerror("Invalid Value",
                                     "Sentence Similarity must be between 50% and 95%.")
                return
            if not (0.05 <= new_novelty <= 0.50):
                messagebox.showerror("Invalid Value",
                                     "Novelty Threshold must be between 5% and 50%.")
                return
            if not (2 <= new_min_words <= 10):
                messagebox.showerror("Invalid Value",
                                     "Min Sentence Words must be between 2 and 10.")
                return
            if not (10 <= new_window <= 100):
                messagebox.showerror("Invalid Value",
                                     "Global Window Size must be between 10 and 100.")
                return

            # Apply to config
            self.capture_config.post_process_sentence_similarity = new_similarity
            self.capture_config.post_process_novelty_threshold = new_novelty
            self.capture_config.post_process_min_sentence_words = new_min_words
            self.capture_config.post_process_global_window_size = new_window

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
                f"Sentence Similarity: {int(new_similarity * 100)}%\n"
                f"Novelty Threshold: {int(new_novelty * 100)}%\n"
                f"Min Sentence Words: {new_min_words}\n"
                f"Global Window Size: {new_window}\n\n"
                f"{save_msg}"
            )

            self.close_dialog()

        except ValueError as e:
            messagebox.showerror("Invalid Values", f"Please enter valid numbers: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")