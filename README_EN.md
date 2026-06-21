# AI-RE Toolkit

All-in-One AI Decompilation Toolkit - Automate binary file reverse analysis with AI-powered intelligent scheduling

English | [中文](README.md)

---

## 🎯 Features

- **Multi-platform Support**: Windows EXE/DLL, Android APK/DEX, iOS IPA, Linux ELF, and more
- **AI Intelligent Scheduling**: AI automatically determines file type and calls appropriate toolchains for analysis
- **Real-time Chat**: Directly instruct AI through dialog to perform operations (analysis, modification, repackaging, etc.)
- **Continuous Execution**: AI can execute multi-step loops until tasks are completed
- **File Operations**: AI can directly read, write, create, and delete files and directories
- **Multi-language Support**: Built-in Chinese/English language switching

## 🚀 Quick Start

### Requirements

- Python 3.10+
- Windows/Linux/macOS

### Installation

```bash
# Clone repository
git clone https://github.com/OrbitSunztoo/ai-re-toolkit.git
cd ai-re-toolkit

# Install dependencies
pip install -r requirements.txt

# One-click startup (Windows)
start.bat
```

### AI Configuration

1. Launch the application and click menu **Settings → AI Configuration**
2. Fill in API URL and Key (Supports OpenAI, DeepSeek, Claude, local Ollama, etc.)
3. Click "Test Connection" to verify and save

## 📖 Usage

### Method 1: AI Automated Analysis

1. Drag or select the file to analyze
2. Click "Start Analysis"
3. AI will automatically execute multi-step analysis workflow

### Method 2: Real-time Chat Commands

Enter commands in the AI chat panel on the right, for example:

- "Analyze this file"
- "Help me unpack this EXE"
- "Modify APK package name to com.test.newpack"
- "Decompile this APK"

AI will automatically call corresponding tools and continue execution until completion.

## 🛠️ Supported Platforms & Analysis Tools

### Windows (EXE/DLL)

| Feature | Tool |
|---------|------|
| File Analysis | pefile, Detect It Easy |
| Unpacking | UPX |
| Decompilation | Ghidra |
| Strings | strings |

### Android (APK)

| Feature | Tool |
|---------|------|
| Package Info | pyaxmlparser |
| Decompilation | JADX |
| Unpack/Repack | APKTool |

### iOS (IPA)

| Feature | Tool |
|---------|------|
| Info Parsing | plistlib, zipfile |
| Strings | strings |

## 🏗️ Project Architecture

```
ai-re-toolkit/
├── src/
│   ├── gui/              # PySide6 GUI Interface
│   │   ├── main_window.py      # Main Window
│   │   ├── ai_chat_panel.py    # AI Chat Panel
│   │   ├── file_panel.py       # File Selection Panel
│   │   ├── code_viewer.py      # Code Viewer
│   │   └── settings_dialog.py  # Settings Dialog
│   ├── ai/               # AI Scheduling Layer
│   │   ├── scheduler.py         # AI Scheduler Core
│   │   └── providers/           # Multi-model Support
│   │       ├── base.py          # Provider Base Class
│   │       ├── openai_provider.py
│   │       └── ollama_provider.py
│   ├── core/             # File Type Recognition
│   │   └── file_analyzer.py
│   ├── tools/            # Tool Executor
│   │   ├── executor.py         # Tool Execution
│   │   ├── registry.py         # Tool Registry
│   │   └── python_tools.py      # Python Native Tools
│   └── utils/            # Utility Modules
│       ├── logger.py            # Logging
│       └── i18n.py              # Internationalization
├── config/               # Configuration Files
├── translations/         # Translation Files
├── tools/                # External Tools Directory
└── start.bat            # Windows Startup Script
```

## 🔧 Technology Stack

- **GUI**: PySide6
- **AI Providers**: Ollama, OpenAI, Claude, DeepSeek, Qwen, Kimi, etc.
- **Reverse Engineering Tools**: pefile, pyaxmlparser, JADX, APKTool, Ghidra, UPX
- **Communication Format**: JSON

## 📦 Build & Release

### Windows

```bash
pip install pyinstaller
python build.py
```

### Linux

```bash
pip install pyinstaller
pyinstaller build.spec
```

## ⚠️ Disclaimer

This software is for **personal program analysis and authorized security auditing only**. It is strictly prohibited to use for illegal cracking of proprietary commercial software. All consequences arising from illegal use of this tool are the responsibility of the user.

## 📄 License

MIT License

## 🙏 Acknowledgments

- [PySide6](https://doc.qt.io/qtforpython/) - Qt for Python
- [pefile](https://github.com/erocarrera/pefile) - PE file analysis
- [JADX](https://github.com/skylot/jadx) - DEX decompiler
- [APKTool](https://github.com/iBotPeaches/Apktool) - APK unpacking tool
- [Ghidra](https://github.com/NationalSecurityAgency/ghidra) - Reverse engineering framework
