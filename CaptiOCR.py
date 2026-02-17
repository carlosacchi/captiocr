#!/usr/bin/env python
"""
CaptiOCR - Main entry point
"""
import sys
import os

def main():
    """Main entry point for CaptiOCR."""
    try:
        # Ensure the captiocr module can be found
        if hasattr(sys, '_MEIPASS'):
            # Running in PyInstaller bundle
            base_path = sys._MEIPASS
        else:
            # Running in development
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        # Add base path to sys.path if not already there
        if base_path not in sys.path:
            sys.path.insert(0, base_path)
        
        # Import and run the main application
        from captiocr.main import main as app_main
        app_main()
        
    except Exception as e:
        # Show error dialog
        error_message = f"Failed to start CaptiOCR:\n\n{str(e)}"
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("CaptiOCR Error", error_message)
            root.destroy()
        except Exception as dialog_error:
            # If dialog fails, create error file
            try:
                import traceback
                with open("captiocr_error.txt", "w") as f:
                    f.write(f"CaptiOCR Error: {str(e)}\n\n")
                    f.write(f"Traceback:\n{traceback.format_exc()}\n\n")
                    f.write(f"Dialog error: {str(dialog_error)}\n")
                print(f"Error logged to captiocr_error.txt: {error_message}", file=sys.stderr)
            except Exception as file_error:
                # Last resort - print to stderr
                print(f"CRITICAL ERROR: {error_message}", file=sys.stderr)
                print(f"Could not create error file: {file_error}", file=sys.stderr)

if __name__ == "__main__":
    main()