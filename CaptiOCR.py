import tkinter as tk
from tkinter import ttk, messagebox
import pytesseract
from PIL import ImageGrab
import keyboard
import os
from datetime import datetime
import threading
import time
import ctypes
import difflib

print("Starting application...")

# Tesseract Configuration
TESSDATA_PREFIX = r'C:\Program Files\Tesseract-OCR\tessdata'
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

print("Setting Tesseract paths...")
os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

class ScreenOCR:
    def __init__(self):
        print("Initializing CaptiOCR...")
        self.root = tk.Tk()
        self.root.title("CaptiOCR Tool")
        
        # Get system DPI scaling
        try:
            awareness = ctypes.c_int()
            ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
            self.scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
            print(f"System DPI scaling detected: {self.scale_factor}")
        except:
            self.scale_factor = self.root.winfo_fpixels('1i') / 96  # fallback method
            print(f"Using fallback scaling method: {self.scale_factor}")
        
        print("Setting variables...")
        # Variables
        self.running = False
        self.selection_window = None
        self.selected_lang = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.capture_thread = None
        self.debug_enabled = tk.BooleanVar(value=False)
        
        print("Getting screen info...")
        # Basic screen info
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        self.monitor_offset_x = 0
        self.monitor_offset_y = 0
        
        print("Setting window size...")
        # Set initial size
        window_width = 350
        window_height = 550
        x = (self.screen_width - window_width) // 2
        y = (self.screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        print("Setting languages...")
        # Language list
        self.languages = [
            ("English", "eng"),
            ("Italian", "ita")
        ]
        
        print("Setting up UI...")
        self.setup_ui()
        print("Initialization complete.")
        
    def setup_ui(self):
        print("Creating main frame...")
        frame = ttk.Frame(self.root, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        print("Adding title...")
        # Title
        title = ttk.Label(frame, text="CaptiOCR Tool", font=("Arial", 20))
        title.grid(row=0, column=0, pady=20)
        
        print("Adding language selection...")
        # Language selection
        lang_frame = ttk.LabelFrame(frame, text="Select Language", padding="10")
        lang_frame.grid(row=1, column=0, pady=10, sticky=(tk.W, tk.E))
        
        combo = ttk.Combobox(lang_frame, textvariable=self.selected_lang)
        combo['values'] = [lang[0] for lang in self.languages]
        combo.current(0)
        combo.pack(pady=5, padx=10, fill='x')
        
        print("Adding debug checkbox...")
        # Debug checkbox
        debug_check = ttk.Checkbutton(frame, text="Enable Debug Logging", variable=self.debug_enabled)
        debug_check.grid(row=2, column=0, pady=10)
        
        print("Adding start button...")
        # Start button
        self.start_button = ttk.Button(frame, text="Start (Select Area)", command=self.start_capture)
        self.start_button.grid(row=3, column=0, pady=20)
        
        print("Adding status label...")
        # Status
        self.status_label = ttk.Label(frame, textvariable=self.status_var)
        self.status_label.grid(row=4, column=0, pady=10)
        
        print("Adding instructions...")
        # Instructions
        instructions = """
        Instructions:
        1. Select language
        2. Click 'Start' and position the yellow area
        3. Press OK to begin OCR
        4. Press Ctrl+Q to stop and exit
        """
        ttk.Label(frame, text=instructions, justify=tk.LEFT).grid(row=5, column=0, pady=20)
        
        # Configure grid
        frame.columnconfigure(0, weight=1)
        print("UI setup complete.")

    def log_debug(self, message):
        if self.debug_enabled.get():
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open("ocr_debug.log", "a", encoding='utf-8') as f:
                f.write(f"{timestamp}: {message}\n")

    def get_lang_code(self):
        selected = self.selected_lang.get()
        return next(lang[1] for lang in self.languages if lang[0] == selected)

    def create_selection_window(self):
        try:
            self.selection_window = tk.Toplevel(self.root)
            self.selection_window.attributes('-alpha', 0.3)
            self.selection_window.attributes('-topmost', True)
            self.selection_window.configure(bg='yellow')
            
            self.selection_window.overrideredirect(True)
            
            # Initialize coordinates
            self.start_x = None
            self.start_y = None
            self.current_x = None
            self.current_y = None
            
            # Set size
            self.current_width = 500
            self.current_height = 150
            
            # Mouse bindings
            self.selection_window.bind('<Button-1>', self.start_drag)
            self.selection_window.bind('<B1-Motion>', self.do_drag)
            self.selection_window.bind('<ButtonRelease-1>', self.end_drag)
            
            # OK button
            ok_button = tk.Button(self.selection_window, text="OK", command=self.start_ocr)
            ok_button.pack(side=tk.TOP, pady=10)
            
            # Stop button
            stop_button = tk.Button(self.selection_window, text="STOP", command=self.stop_capture)
            stop_button.pack(side=tk.TOP, pady=10)

            # Center window
            x = (self.screen_width - self.current_width) 
            y = (self.screen_height - self.current_height) 
            self.selection_window.geometry(f"{self.current_width}x{self.current_height}+{x}+{y}")
            
            self.current_x = x
            self.current_y = y
            
            self.log_debug(f"Selection window created at x={x}, y={y}")
            
        except Exception as e:
            self.log_debug(f"Error creating selection window: {str(e)}")
            raise

    def start_drag(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def do_drag(self, event):
        try:
            if self.start_x is not None and self.start_y is not None:
                real_x = event.x_root - self.monitor_offset_x
                real_y = event.y_root - self.monitor_offset_y
                
                new_x = real_x - self.start_x
                new_y = real_y - self.start_y
                
                print(f"During drag - Mouse: ({event.x_root}, {event.y_root}), Window: ({new_x}, {new_y})")
                self.selection_window.geometry(f"+{new_x}+{new_y}")
                self.current_x = real_x
                self.current_y = real_y
                
        except Exception as e:
            print(f"Error during drag: {str(e)}")

    def end_drag(self, event):
        try:
            raw_x = self.selection_window.winfo_rootx()
            raw_y = self.selection_window.winfo_rooty()
            
            self.current_x = int(raw_x * self.scale_factor)
            self.current_y = int(raw_y * self.scale_factor)
            
            print(f"=== Drag End ===")
            print(f"System scaling factor: {self.scale_factor}")
            print(f"Mouse position: ({event.x_root}, {event.y_root})")
            print(f"Raw window position: ({raw_x}, {raw_y})")
            print(f"Scaled position: ({self.current_x}, {self.current_y})")
            
        except Exception as e:
            print(f"Error ending drag: {str(e)}")
            
    def text_similarity(self, text1, text2):
        """Calculate similarity ratio between two texts"""
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def capture_screen(self):
        try:
            print("Starting capture process")
            self.status_var.set("Capturing... (Press Ctrl+Q to stop)")
            
            last_text = ""
            output_file = f"capture_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}.txt"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Caption capture started: {datetime.now()}\n\n")
            
            while self.running:
                try:
                    # Use scaled coordinates for capture
                    x = int(self.selection_window.winfo_rootx() * self.scale_factor)
                    y = int(self.selection_window.winfo_rooty() * self.scale_factor)
                    width = int(self.selection_window.winfo_width() * self.scale_factor)
                    height = int(self.selection_window.winfo_height() * self.scale_factor)
                    
                    screenshot = ImageGrab.grab(bbox=(x, y, x+width, y+height))
                    text = pytesseract.image_to_string(screenshot, lang=self.get_lang_code()).strip()
                    
                    # Only save if text is significantly different (less than 90% similar)
                    if text and self.text_similarity(text, last_text) < 0.9:
                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
                        last_text = text
                        self.status_var.set(f"Last capture: {text[:50]}...")
                    
                    if keyboard.is_pressed('ctrl+q'):
                        print("Ctrl+Q pressed, stopping capture")
                        self.stop_capture()
                        break
                        
                    time.sleep(2)  # Increased to 2 seconds
                        
                except Exception as e:
                    print(f"Error during capture iteration: {str(e)}")
                    time.sleep(1)
                    
        except Exception as e:
            print(f"Critical error in capture_screen: {str(e)}")
            self.stop_capture()

    def start_capture(self):
        try:
            print("Starting capture process")
            self.status_var.set("Select area and press OK")
            self.create_selection_window()
            self.start_button.state(['disabled'])
        except Exception as e:
            print(f"Error in start_capture: {str(e)}")
            messagebox.showerror("Error", f"Failed to start capture: {str(e)}")

    def start_ocr(self):
        try:
            print("Starting OCR process")
            self.running = True
            self.capture_thread = threading.Thread(target=self.capture_screen)
            self.capture_thread.daemon = True
            self.capture_thread.start()
        except Exception as e:
            print(f"Error in start_ocr: {str(e)}")
            messagebox.showerror("Error", f"Failed to start OCR: {str(e)}")

    def stop_capture(self):
        try:
            print("Stopping capture")
            self.running = False
            if self.selection_window:
                self.selection_window.destroy()
                self.selection_window = None
            self.start_button.state(['!disabled'])
        except Exception as e:
            print(f"Error in stop_capture: {str(e)}")

    def run(self):
        try:
            print("Starting main loop")
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except Exception as e:
            print(f"Error in run: {str(e)}")
    
    def on_closing(self):
        try:
            print("Closing application")
            self.stop_capture()
            self.root.destroy()
        except Exception as e:
            print(f"Error in on_closing: {str(e)}")

if __name__ == "__main__":
    try:
        print("Creating application instance...")
        app = ScreenOCR()
        print("Running application...")
        app.run()
    except Exception as e:
        print(f"Critical error: {str(e)}")
        input("Press Enter to exit...")