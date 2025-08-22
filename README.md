# 🖥️ CaptiOCR - Real-Time Screen Text Extraction

[![CodeQL](https://github.com/carlosacchi/captiocr/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/carlosacchi/captiocr/actions/workflows/github-code-scanning/codeql)

**CaptiOCR** is an open-source **real-time screen text extraction tool** designed to capture and transcribe captions (subtitles) from video conferencing applications like **Microsoft Teams**, **Zoom**, and **Google Meet**. With an intuitive interface and powerful OCR capabilities, you can select any screen area and extract text continuously in real-time.

🚀 **Latest Version: 0.12.00** - Now with comprehensive **multi-monitor support** and **DPI awareness**!

---

## ✨ Key Features

✅ **Real-time OCR processing** using [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)  
✅ **Multi-language support** (English, Italian, French, German, Portuguese)  
✅ **Multi-monitor support** with DPI awareness  
✅ **Dynamic area selection** - drag, resize, and move capture areas during operation  
✅ **Text processing** - automatic duplicate removal and text cleaning  
✅ **Profile management** - save and load different configurations  
✅ **Hotkey support** - `Ctrl+Q` to stop capture  
✅ **Export options** - save captured text with custom naming  
✅ **Debug logging** for troubleshooting  
✅ **Modular architecture** - clean, maintainable codebase  

---

## 🛠️ Prerequisites

Before installation, ensure you have:
- ✅ **Python 3.8+** installed  
- ✅ **Tesseract OCR** installed ([Download here](https://github.com/tesseract-ocr/tesseract))  
- ✅ **Windows OS** (primary support)  

---

## 📦 Installation

### **1️⃣ Clone the Repository**
```bash
git clone https://github.com/CarloSacchi/CaptiOCR.git
cd CaptiOCR
```

### **2️⃣ Install Python Dependencies**
```bash
pip install -r requirements.txt
```

### **3️⃣ Install Tesseract OCR**

**Windows users:**  
Download and install Tesseract from the [official releases](https://github.com/tesseract-ocr/tesseract/releases).  
The application will automatically detect standard installation paths.

---

## 🚀 Quick Start

Run the application:
```bash
python CaptiOCR.py
```

### **Basic Usage:**

1️⃣ **Select Language** - Choose your OCR language from the dropdown  
2️⃣ **Click "Start (Select Area)"** - Open the area selection tool  
3️⃣ **Drag to Select** - Draw a rectangle around the text area you want to capture  
4️⃣ **Press ENTER** - Begin real-time text extraction  
5️⃣ **Press Ctrl+Q or STOP** - End the capture session  
6️⃣ **Name Your Capture** - Save with a custom filename  

📁 **Output:** Captured text is saved in the `captures/` folder as timestamped `.txt` files.

---

## 🎯 Advanced Features

### **Multi-Monitor Support**
- **Automatic detection** of all connected monitors
- **DPI awareness** for high-resolution displays
- **Cross-monitor selection** - capture areas spanning multiple screens
- **Monitor-specific positioning** for consistent setups

### **Dynamic Capture Areas**
- **Resizable borders** - adjust capture area during operation
- **Movable windows** - reposition without stopping capture
- **Multiple profiles** - save configurations for different applications

### **Text Processing**
- **Duplicate detection** - automatic removal of repeated text
- **Text cleaning** - remove artifacts and formatting issues
- **Processed output** - clean, readable transcriptions

### **Profile Management**
- **Save Settings** - store optimized configurations
- **Quick Load** - switch between saved profiles
- **Application-specific** - different settings for Teams, Zoom, Meet

---

## 💡 Tips & Best Practices

### **Optimizing OCR Accuracy**
- **Language Selection**: Choose the correct language model for best results with accents and special characters
- **Capture Area**: Select narrow, wide rectangles focusing on subtitle regions
- **Minimum Size**: Ensure capture areas are at least 50×50 pixels
- **Stable Areas**: Target regions where text appears consistently

### **Performance Optimization**
- **Close unnecessary applications** to reduce system load
- **Use specific language models** rather than auto-detection
- **Regular cleanup** of old capture files and logs
- **Monitor system resources** during extended capture sessions

---

## 📁 Project Structure

```
CaptiOCR/
├── CaptiOCR.py              # Main application entry point
├── captiocr/                # Core application modules
│   ├── config/              # Settings and constants
│   ├── core/                # OCR and capture logic
│   ├── models/              # Data models
│   ├── ui/                  # User interface components
│   └── utils/               # Utilities and helpers
├── captures/                # Saved text outputs
├── config/                  # User preferences
├── tessdata/                # OCR language files
├── logs/                    # Application logs
└── resources/               # Icons and assets
```

---

## 🔧 Configuration

The application uses JSON configuration files stored in `config/`:
- **User preferences** - UI settings, language choices
- **Language data** - Available OCR models
- **Capture profiles** - Saved area configurations

---

## 📋 System Requirements

- **OS**: Windows 10/11 (primary), Linux/macOS (experimental)
- **RAM**: 4GB minimum, 8GB recommended
- **CPU**: Multi-core processor recommended for real-time processing
- **Display**: Support for multiple monitors with varying DPI
- **Storage**: 100MB+ for application and language files

---

## 🐛 Troubleshooting

### **Common Issues:**
- **OCR not working**: Verify Tesseract installation and PATH
- **Text not detected**: Check language selection and capture area size
- **Performance issues**: Close other applications, check system resources
- **Multi-monitor problems**: Update display drivers, check DPI settings

### **Debug Logging:**
Enable debug logging in the application settings to capture detailed operation information for troubleshooting.

---

## 🗺️ Roadmap

### **Current Version (0.12.00)**
- ✅ Multi-monitor support with DPI awareness
- ✅ Modular, maintainable codebase
- ✅ Enhanced text processing
- ✅ Improved error handling

### **Upcoming Features**
- 🔄 **Live translation** integration
- 🔄 **Cloud storage** synchronization  
- 🔄 **Export formats** (PDF, HTML, Word)
- 🔄 **API integration** for external applications
- 🔄 **Dark mode** and theme customization
- 🔄 **Batch processing** capabilities

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Follow** the coding guidelines in `CLAUDE.md`
4. **Commit** your changes (`git commit -m 'Add amazing feature'`)
5. **Push** to the branch (`git push origin feature/amazing-feature`)
6. **Open** a Pull Request

### **Development Guidelines**
- Follow **PEP 8** Python style guide
- Use **type hints** and **docstrings**
- Maintain **modular architecture**
- Add **comprehensive logging**
- Update **version numbers** for functional changes

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 👤 Author & Support

**Author:** Carlo Sacchi  
**Website:** [https://www.captiocr.com](https://www.captiocr.com)  
**Version:** 0.12.00 (August 2025)

For support, feature requests, or bug reports, please open an issue on GitHub.

---

**⭐ If CaptiOCR helps you, please consider giving it a star on GitHub!**