"""
Main entry point for CaptiOCR application.
"""
import sys
import logging
from pathlib import Path

# Always use absolute imports for exe compatibility
from captiocr.ui.main_window import MainWindow
from captiocr.utils.logger import LoggerSetup, get_logger
from captiocr.utils.file_manager import FileManager
from captiocr.config.constants import APP_NAME, APP_VERSION


def main():
    """Main application entry point."""
    try:
        # Initialize logging (simplified for exe)
        try:
            LoggerSetup()
            logger = get_logger('CaptiOCR.Main')
            logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
        except:
            # If logging fails, continue without it
            logger = None
        
        # Clean old log files (skip if fails)
        try:
            FileManager.clean_old_logs(keep_recent=20)
        except:
            pass
        
        # Create and run main window
        app = MainWindow()
        app.run()
        
        if logger:
            logger.info(f"{APP_NAME} closed")
        
    except Exception as e:
        # Always try to show error dialog
        error_shown = False
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "CaptiOCR Error",
                f"Failed to start CaptiOCR:\n\n{str(e)}\n\n"
                f"Error type: {type(e).__name__}"
            )
            root.destroy()
            error_shown = True
        except:
            pass
        
        # If dialog failed, create error file
        if not error_shown:
            try:
                with open("captiocr_main_error.txt", "w") as f:
                    f.write(f"CaptiOCR Main Error: {str(e)}\nType: {type(e).__name__}")
            except:
                pass


if __name__ == "__main__":
    main()