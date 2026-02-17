"""
Main entry point for CaptiOCR application.
"""
import sys
import ctypes

# Always use absolute imports for exe compatibility
from captiocr.ui.main_window import MainWindow
from captiocr.utils.logger import LoggerSetup, get_logger
from captiocr.utils.file_manager import FileManager
from captiocr.config.constants import APP_NAME, APP_VERSION


def set_dpi_awareness():
    """Set DPI awareness for accurate multi-monitor DPI detection."""
    if sys.platform != 'win32':
        return
    
    try:
        # Try the most modern DPI awareness first (Windows 10 1703+)
        DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        result = ctypes.windll.user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        if result:
            print("DPI awareness set to PER_MONITOR_AWARE_V2")
            return
    except Exception as e:
        print(f"SetProcessDpiAwarenessContext failed: {e}")
    
    try:
        # Fallback to older API (Windows 8.1+)
        PROCESS_PER_MONITOR_DPI_AWARE = 2
        result = ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
        if result == 0:  # S_OK
            print("DPI awareness set to PROCESS_PER_MONITOR_DPI_AWARE")
            return
    except Exception as e:
        print(f"SetProcessDpiAwareness failed: {e}")
    
    try:
        # Final fallback to basic DPI awareness (Windows Vista+)
        result = ctypes.windll.user32.SetProcessDPIAware()
        if result:
            print("DPI awareness set to basic DPI_AWARE")
            return
    except Exception as e:
        print(f"SetProcessDPIAware failed: {e}")
    
    print("Warning: Could not set DPI awareness - DPI detection may be inaccurate")


def main():
    """Main application entry point."""
    try:
        # Set DPI awareness before any GUI operations
        set_dpi_awareness()
        
        # Initialize logging (simplified for exe)
        try:
            LoggerSetup()
            logger = get_logger('CaptiOCR.Main')
            logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
        except Exception as log_error:
            # If logging fails, continue without it
            print(f"Warning: Logging initialization failed: {log_error}", file=sys.stderr)
            logger = None

        # Clean old log files (skip if fails)
        try:
            FileManager.clean_old_logs(keep_recent=20)
        except Exception as clean_error:
            if logger:
                logger.warning(f"Failed to clean old logs: {clean_error}")
            else:
                print(f"Warning: Failed to clean old logs: {clean_error}", file=sys.stderr)
        
        # Create and run main window
        app = MainWindow()
        app.run()
        
        if logger:
            logger.info(f"{APP_NAME} closed")
        
    except Exception as e:
        # Always try to show error dialog
        import traceback
        error_shown = False
        error_details = (
            f"Failed to start CaptiOCR:\n\n{str(e)}\n\n"
            f"Error type: {type(e).__name__}"
        )

        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("CaptiOCR Error", error_details)
            root.destroy()
            error_shown = True
        except Exception as dialog_error:
            print(f"Error showing dialog: {dialog_error}", file=sys.stderr)

        # If dialog failed or succeeded, always create error file for debugging
        try:
            with open("captiocr_main_error.txt", "w") as f:
                f.write(f"CaptiOCR Main Error: {str(e)}\n")
                f.write(f"Type: {type(e).__name__}\n\n")
                f.write(f"Traceback:\n{traceback.format_exc()}\n")
            if not error_shown:
                print(f"Error details written to captiocr_main_error.txt", file=sys.stderr)
        except Exception as file_error:
            print(f"CRITICAL: Could not write error file: {file_error}", file=sys.stderr)
            print(f"Original error: {error_details}", file=sys.stderr)


if __name__ == "__main__":
    main()