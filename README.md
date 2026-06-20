# AI-RE Toolkit

一体化AI反编译工具箱 - 借助AI智能调度自动完成二进制文件逆向分析

[English](README.md) | 中文

---

## 🎯 功能特性

- **多平台支持**: Windows EXE/DLL、Android APK/DEX、iOS IPA、Linux ELF 等
- **AI智能调度**: AI自动判断文件类型，调用合适的工具链进行分析
- **实时对话**: 通过对话框实时指令AI执行操作（分析、修改、打包等）
- **持续执行**: AI可多步循环执行，直到任务完成
- **文件操作**: AI可直接读取、写入、创建、删除文件和目录

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Windows/Linux/macOS

### 安装

```bash
# 克隆项目
git clone https://github.com/yourname/ai-re-toolkit.git
cd ai-re-toolkit

# 安装依赖
pip install -r requirements.txt

# 一键启动（Windows）
start.bat
```

### AI配置

1. 启动程序后，点击菜单 **设置 → AI配置**
2. 填写 API 地址和 Key（支持 OpenAI、DeepSeek、Claude、本地 Ollama 等）
3. 点击"测试连接"确认后保存

## 📖 使用方式

### 方式一：AI自动化分析

1. 拖拽或选择要分析的文件
2. 点击"开始AI分析"
3. AI会自动执行多步分析流程

### 方式二：实时对话指令

在右侧AI对话面板输入指令，例如：

- "分析这个文件"
- "帮我脱壳这个EXE"
- "修改APK的包名为 com.test.newpack"
- "反编译这个APK"

AI会自动调用相应工具并持续执行直到完成。

## 🛠️ 支持的平台与分析工具

### Windows (EXE/DLL)

| 功能 | 工具 |
|------|------|
| 文件分析 | pefile, Detect It Easy |
| 脱壳 | UPX |
| 反编译 | Ghidra |
| 字符串 | strings |

### Android (APK)

| 功能 | 工具 |
|------|------|
| 包信息 | pyaxmlparser |
| 反编译 | JADX |
| 拆包/重打包 | APKTool |

### iOS (IPA)

| 功能 | 工具 |
|------|------|
| 信息解析 | plistlib, zipfile |
| 字符串 | strings |

## 🏗️ 项目架构

```
ai-re-toolkit/
├── src/
│   ├── gui/              # PySide6 GUI界面
│   │   ├── main_window.py      # 主窗口
│   │   ├── ai_chat_panel.py    # AI对话面板
│   │   ├── file_panel.py       # 文件选择面板
│   │   └── code_viewer.py      # 代码查看器
│   ├── ai/               # AI调度层
│   │   ├── scheduler.py         # AI调度核心
│   │   └── providers/           # 多模型支持
│   │       ├── base.py          # Provider基类
│   │       ├── openai_provider.py
│   │       ├── ollama_provider.py
│   │       └── other_providers.py
│   ├── core/             # 文件类型识别
│   │   └── file_analyzer.py
│   └── tools/            # 工具执行器
│       ├── executor.py         # 工具调用
│       ├── registry.py         # 工具注册表
│       └── python_tools.py      # Python原生工具
├── config/               # 配置文件
├── tools/                # 外部工具目录
└── start.bat            # Windows启动脚本
```

## 🔧 技术栈

- **GUI**: PySide6
- **AI调度**: 支持 Ollama/OpenAI/Claude/DeepSeek/Qwen/Kimi 等
- **逆向工具**: pefile, pyaxmlparser, JADX, APKTool, Ghidra, UPX
- **通信格式**: JSON

## 📦 打包发布

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

## ⚠️ 免责声明

本软件仅用于**自有程序分析和授权安全审计**，严禁用于非法破解闭源商用软件。所有使用本工具进行非法操作所产生的后果由使用者自行承担。

## 📄 许可证

MIT License

## 🙏 致谢

- [PySide6](https://doc.qt.io/qtforpython/) - Qt for Python
- [pefile](https://github.com/erocarrera/pefile) - PE文件分析
- [JADX](https://github.com/skylot/jadx) - DEX反编译器
- [APKTool](https://github.com/iBotPeaches/Apktool) - APK拆包工具
- [Ghidra](https://github.com/NationalSecurityAgency/ghidra) - 逆向工程框架
