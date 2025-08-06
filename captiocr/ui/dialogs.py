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
        """Perform the actual download."""
        def progress_callback(message: str):
            self.status_label.config(text=message)
            self.window.update()
        
        # Download the language
        success = self.language_manager.download_language(
            lang_code,
            TESSDATA_DIR,
            progress_callback
        )
        
        if success:
            self.download_success = True
            self.status_label.config(text="Download complete!")
            self.progress_bar.stop()
            
            # Update window and close after delay (like original)
            self.window.update()
            self.parent.after(2000, self.window.destroy)
        else:
            self.progress_bar.stop()
            messagebox.showerror(
                "Download Failed",
                f"Failed to download {lang_code} language file"
            )
            # always release grab before destroying
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