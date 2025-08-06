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
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "CaptiOCR Error",
                f"Failed to start CaptiOCR:\n\n{str(e)}"
            )
            root.destroy()
        except:
            # If dialog fails, create error file
            try:
                with open("captiocr_error.txt", "w") as f:
                    f.write(f"CaptiOCR Error: {str(e)}")
            except:
                pass

if __name__ == "__main__":
    main()