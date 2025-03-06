import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pytesseract
from PIL import ImageGrab
import keyboard
import os
import sys
import re
from datetime import datetime
import threading
import time
import ctypes
import difflib
import pathlib

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
        
        # Create the output directory
        self.setup_output_directory()
        
        # Track the most recently processed file
        self.last_processed_file = None
        self.current_capture_timestamp = None
        
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
        
        print("Setting window size...")
        # Set initial size
        window_width = 300
        window_height = 550
        x = (self.screen_width - window_width) // 2
        y = (self.screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.root.minsize(window_width, window_height)
        self.root.maxsize(window_width, window_height)
        
        print("Setting languages...")
        # Language list
        self.languages = [
            ("English", "eng"),
            ("Italian", "ita")
        ]
        
        print("Setting up UI...")
        self.setup_ui()
        print("Initialization complete.")
    
    def setup_output_directory(self):
        """Create 'captures' directory in the same folder as the script"""
        try:
            # Get the path of the script
            if getattr(sys, 'frozen', False):
                # For compiled executables
                script_path = os.path.dirname(sys.executable)
            else:
                # For .py script
                script_path = os.path.dirname(os.path.abspath(__file__))
            
            # Create captures directory
            self.capture_dir = os.path.join(script_path, "captures")
            os.makedirs(self.capture_dir, exist_ok=True)
            print(f"Output directory set to: {self.capture_dir}")
            self.log_debug(f"Output directory created at: {self.capture_dir}")
        except Exception as e:
            print(f"Error creating output directory: {str(e)}")
            # Fallback to current directory
            self.capture_dir = "captures"
            os.makedirs(self.capture_dir, exist_ok=True)
        
    def setup_ui(self):
        print("Creating main frame...")
        frame = ttk.Frame(self.root, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        print("Adding title...")
        # Title
        title = ttk.Label(frame, text="CaptiOCR Exp Tool", font=("Arial", 20))
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
        
        print("Adding caption display area...")
        # Caption display area
        caption_frame = ttk.LabelFrame(frame, text="Captured Text", padding="10")
        caption_frame.grid(row=5, column=0, pady=5, sticky=(tk.W, tk.E))
        
        print("Adding instructions...")
        # Instructions
        instructions = """
        Instructions:
        1. Select language
        2. Click 'Start' and position the yellow area
        3. Press OK to begin OCR
        4. Press Ctrl+Q or STOP to stop OCR
        """
        ttk.Label(frame, text=instructions, justify=tk.LEFT).grid(row=5, column=0, pady=20)
        
        # Configure grid
        frame.columnconfigure(0, weight=1)
        print("UI setup complete.")

    def log_debug(self, message):
        if self.debug_enabled.get():
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_path = os.path.join(self.capture_dir, "ocr_debug.log")
            with open(log_path, "a", encoding='utf-8') as f:
                f.write(f"{timestamp}: {message}\n")

    def get_lang_code(self):
        selected = self.selected_lang.get()
        return next(lang[1] for lang in self.languages if lang[0] == selected)

    def create_selection_window(self):
        try:
            self.selection_window = tk.Toplevel(self.root)
            self.selection_window.attributes('-alpha', 0.2)
            self.selection_window.attributes('-topmost', True)
            self.selection_window.configure(bg='yellow')
            
            self.selection_window.overrideredirect(True)
        
            # Initialize coordinates
            self.start_x = None
            self.start_y = None
            
            # Set size
            self.current_width = 550
            self.current_height = 160
            
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

            # Center window properly
            x = (self.screen_width - self.current_width) // 2
            y = (self.screen_height - self.current_height) // 2
            self.selection_window.geometry(f"{self.current_width}x{self.current_height}+{x}+{y}")
            
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
                # Calculate new position directly
                new_x = event.x_root - self.start_x
                new_y = event.y_root - self.start_y
                
                print(f"During drag - Mouse: ({event.x_root}, {event.y_root}), Window: ({new_x}, {new_y})")
                self.selection_window.geometry(f"+{new_x}+{new_y}")
                
        except Exception as e:
            print(f"Error during drag: {str(e)}")

    def end_drag(self, event):
        try:
            raw_x = self.selection_window.winfo_rootx()
            raw_y = self.selection_window.winfo_rooty()
            
            # Log the position values
            scaled_x = int(raw_x * self.scale_factor)
            scaled_y = int(raw_y * self.scale_factor)
            
            print(f"=== Drag End ===")
            print(f"System scaling factor: {self.scale_factor}")
            print(f"Mouse position: ({event.x_root}, {event.y_root})")
            print(f"Raw window position: ({raw_x}, {raw_y})")
            print(f"Scaled position: ({scaled_x}, {scaled_y})")
            
        except Exception as e:
            print(f"Error ending drag: {str(e)}")
            
    def text_similarity(self, text1, text2):
        """Calculate similarity ratio between two texts"""
        return difflib.SequenceMatcher(None, text1, text2).ratio()
        
    def extract_sentences(self, text):
        """Split text into sentences for better comparison"""
        if not text:
            return []
        # Split by common sentence terminators
        sentences = []
        for part in re.split(r'[.!?]+', text):
            part = part.strip()
            if part:
                sentences.append(part)
        return sentences
        
    def has_significant_new_content(self, new_text, previous_text, threshold=0.95):
        """
        Check if new text has enough unique content compared to previous text
        using sentence-level comparison instead of whole text comparison
        """
        if not previous_text:
            return True
            
        # Extract sentences from both texts
        new_sentences = self.extract_sentences(new_text)
        prev_sentences = self.extract_sentences(previous_text)
        
        if not new_sentences:
            return False
            
        # Count how many new sentences are not in the previous text
        new_sentence_count = 0
        for new_sentence in new_sentences:
            is_new = True
            for prev_sentence in prev_sentences:
                # If the sentence is very similar to a previous one, it's not new
                if len(new_sentence) > 5 and len(prev_sentence) > 5:
                    similarity = self.text_similarity(new_sentence, prev_sentence)
                    if similarity > threshold:
                        is_new = False
                        break
            
            if is_new:
                new_sentence_count += 1
                
        # If at least 25% of sentences are new, consider it significant new content
        return new_sentence_count >= max(1, len(new_sentences) * 0.25)

    def capture_screen(self):
        try:
            print("Starting capture process")
            self.status_var.set("Capturing... (Press Ctrl+Q to stop)")
            
            last_text = ""
            # Create output file in the capture directory
            timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
            self.current_capture_timestamp = timestamp
            filename = f"capture_{timestamp}.txt"
            output_file = os.path.join(self.capture_dir, filename)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Caption capture started: {datetime.now()}\n\n")
            
            # Track consecutive similar captures to adapt the capture interval
            similar_captures_count = 0
            capture_interval = 3  # Start with 3 seconds interval
            
            while self.running:
                try:
                    # Use window functions to get coordinates directly
                    x = int(self.selection_window.winfo_rootx() * self.scale_factor)
                    y = int(self.selection_window.winfo_rooty() * self.scale_factor)
                    width = int(self.selection_window.winfo_width() * self.scale_factor)
                    height = int(self.selection_window.winfo_height() * self.scale_factor)
                    
                    screenshot = ImageGrab.grab(bbox=(x, y, x+width, y+height))
                    text = pytesseract.image_to_string(screenshot, lang=self.get_lang_code()).strip()
                    
                    # Filter out common OCR noise markers
                    text = re.sub(r'\b(ox|ox\s*\||s10|570°|STOP)\b', '', text)
                    text = re.sub(r'\s{2,}', ' ', text).strip()  # Remove multiple spaces
                    
                    # Check if the text has significant new content compared to the last saved text
                    if text and self.has_significant_new_content(text, last_text):
                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
                        last_text = text
                        self.status_var.set(f"Last capture: {text[:50]}...")
                        similar_captures_count = 0
                        
                        # If we captured new content, we can reset the interval back to normal
                        if capture_interval > 3:
                            capture_interval = 3
                    else:
                        # If no significant new content, increment counter and potentially adjust interval
                        similar_captures_count += 1
                        if similar_captures_count > 3:
                            # If we've had multiple similar captures, increase the interval 
                            # to reduce the chance of capturing duplicate content
                            capture_interval = min(capture_interval + 1, 5)  # Max 5 seconds
                    
                    if keyboard.is_pressed('ctrl+q'):
                        print("Ctrl+Q pressed, stopping capture")
                        self.stop_capture()
                        break
                    
                    # Log the current capture status and interval
                    self.log_debug(f"Capture interval: {capture_interval}s, Similar captures: {similar_captures_count}")
                    
                    # Dynamic sleep time based on the capture interval
                    time.sleep(capture_interval)
                        
                except Exception as e:
                    print(f"Error during capture iteration: {str(e)}")
                    self.log_debug(f"Capture error: {str(e)}")
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

    def prompt_for_filename(self):
        """Ask user for a name to include in the processed filename"""
        try:
            filename = simpledialog.askstring("Save As", "Enter a name for the captured file:",
                                              parent=self.root)
            if filename:
                # Remove spaces and special characters
                filename = re.sub(r'[^\w\-]', '_', filename)
                return filename
            return None
        except Exception as e:
            print(f"Error prompting for filename: {str(e)}")
            return None

    def stop_capture(self):
        try:
            print("Stopping capture")
            self.running = False
            
            latest_file = self.find_latest_capture_file()
            if latest_file and (self.last_processed_file != latest_file):
                # Ask user for a name
                custom_name = self.prompt_for_filename()
                
                # Process the file regardless if there's a custom name or not
                self.post_process_capture_file(latest_file, custom_name)
                self.last_processed_file = latest_file
                
                if custom_name:
                    self.status_var.set(f"Capture stopped and saved with name: {custom_name}")
                else:
                    self.status_var.set("Capture stopped and processed with default name")
            else:
                self.status_var.set("Capture stopped (no new file to process)")
                
            if self.selection_window:
                self.selection_window.destroy()
                self.selection_window = None
            self.start_button.state(['!disabled'])
        except Exception as e:
            print(f"Error in stop_capture: {str(e)}")
            self.log_debug(f"Error stopping capture: {str(e)}")
            
    def on_closing(self):
        try:
            print("Closing application")
            self.stop_capture()
            
            self.root.destroy()
            print(f"Files saved in: {self.capture_dir}")
        except Exception as e:
            print(f"Error in on_closing: {str(e)}")

    def run(self):
        try:
            print("Starting main loop")
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except Exception as e:
            print(f"Error in run: {str(e)}")
            
    def find_latest_capture_file(self):
        """Find the most recent capture file in the capture directory, ignoring processed files"""
        try:
            # Only consider original capture files (not already processed ones)
            files = [f for f in os.listdir(self.capture_dir) 
                if f.startswith("capture_") 
                and f.endswith(".txt")
                and not "_processed" in f  # Skip already processed files
                and re.match(r'^capture_\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.txt$', f)]  # Match timestamp format
                    
            if not files:
                return None
                
            files.sort(reverse=True)  # Latest file first
            return os.path.join(self.capture_dir, files[0])
        except Exception as e:
            print(f"Error finding latest file: {str(e)}")
            return None
            
    def post_process_capture_file(self, filepath, custom_name=None):
        """Remove remaining duplications from the capture file and save with custom name if provided"""
        try:
            print(f"Post-processing capture file: {filepath}")
            
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Extract timestamp blocks
            blocks = []
            current_block = []
            timestamp_pattern = re.compile(r'^\[\d{2}:\d{2}:\d{2}\]')
            
            for line in lines:
                if timestamp_pattern.match(line):
                    if current_block:
                        blocks.append(current_block)
                    current_block = [line]
                elif current_block:
                    current_block.append(line)
                    
            if current_block:
                blocks.append(current_block)
                
            # Filter out blocks with duplicate content
            unique_blocks = [blocks[0]]  # Keep the first block
            
            for i in range(1, len(blocks)):
                current_text = ''.join(blocks[i])
                is_unique = True
                
                # Compare with previous blocks
                for prev_block in unique_blocks[-3:]:  # Check against last 3 unique blocks
                    prev_text = ''.join(prev_block)
                    # If similarity is too high, skip this block
                    if self.text_similarity(current_text, prev_text) > 0.75:
                        is_unique = False
                        break
                        
                if is_unique:
                    unique_blocks.append(blocks[i])
            
            # Use the timestamp from the original capture for the processed file
            timestamp = self.current_capture_timestamp
            if not timestamp:
                # Fallback: Extract timestamp from the filename
                base_filename = os.path.basename(filepath)
                timestamp_match = re.match(r'^capture_(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})\.txt$', base_filename)
                if timestamp_match:
                    timestamp = timestamp_match.group(1)
                else:
                    # If all else fails, use current timestamp
                    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
            
            # Create the processed filename with the required format
            if custom_name:
                # Se l'utente ha fornito un nome, usalo all'inizio
                processed_filename = f"{custom_name}_capture_{timestamp}_processed.txt"
            else:
                # Se l'utente ha premuto "Cancel" o ha lasciato il campo vuoto, usa il formato predefinito
                processed_filename = f"capture_{timestamp}_processed.txt"
                
            processed_filepath = os.path.join(self.capture_dir, processed_filename)
            
            # Write back the filtered content
            with open(processed_filepath, 'w', encoding='utf-8') as f:
                f.write(''.join([''.join(block) for block in unique_blocks]))
                
            print(f"Original blocks: {len(blocks)}, After processing: {len(unique_blocks)}")
            print(f"Processed file saved as: {processed_filepath}")
            
        except Exception as e:
            print(f"Error in post-processing: {str(e)}")

if __name__ == "__main__":
    try:
        print("Creating application instance...")
        app = ScreenOCR()
        print("Running application...")
        app.run()
    except Exception as e:
        print(f"Critical error: {str(e)}")
        input("Press Enter to exit...")