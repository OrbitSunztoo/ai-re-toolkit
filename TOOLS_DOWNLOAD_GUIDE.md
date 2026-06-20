# 逆向工具手动下载指南

由于自动下载速度慢，请手动下载以下工具并放入对应目录：

## 📦 核心工具（必须）

### 1. strings（Windows字符串提取）
- 下载地址：https://docs.microsoft.com/en-us/sysinternals/downloads/strings
- 或国内镜像：https://yun.d真正.url/
- 放置位置：`tools/windows/strings/strings.exe`
- 直接下载 exe 即可

### 2. UPX（脱壳工具）
- 下载地址：https://github.com/upx/upx/releases
- 选择文件：`upx-4.2.x-win64.zip`（约3MB）
- 国内加速：`https://ghproxy.com/https://github.com/upx/upx/releases/download/v4.2.4/upx-4.2.4-win64.zip`
- 放置位置：`tools/windows/upx/upx.exe`

### 3. Detect It Easy（查壳工具）
- 下载地址：https://github.com/horsicq/Detect-It-Easy/releases
- 选择文件：`DIE_windows_x64_portable.zip`
- 国内加速：`https://ghproxy.com/https://github.com/horsicq/Detect-It-Easy/releases/download/v3.10/DIE_windows_x64_3.10_portable.zip`
- 放置位置：`tools/windows/die/diec.exe`

### 4. JADX（APK反编译器）
- 下载地址：https://github.com/skylot/jadx/releases
- 选择文件：`jadx-1.5.1.zip`（约40MB）
- 国内加速：`https://ghproxy.com/https://github.com/skylot/jadx/releases/download/v1.5.1/jadx-1.5.1.zip`
- 放置位置：`tools/windows/jadx/`

### 5. APKTool（APK拆包/重打包）
- 下载地址：https://github.com/iBotPeaches/Apktool/releases
- 需要下载：`apktool.jar` + `apktool.bat`
- 国内加速：`https://ghproxy.com/https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar`
- 放置位置：`tools/windows/apktool/`

---

## 🎯 推荐下载顺序

1. **strings.exe** - 最快（几百KB）
2. **UPX** - 小文件（3MB）
3. **Detect It Easy** - 中等（20MB）
4. **JADX** - 较大（40MB）
5. **APKTool** - 很小（几MB）

---

## 📁 目录结构示例

下载后，确保目录结构如下：

```
tools/windows/
├── strings/
│   └── strings.exe          ← 从Strings.zip解压得到
├── upx/
│   ├── upx.exe             ← 从upx-*-win64.zip解压得到
│   └── upx.dll
├── die/
│   └── diec.exe            ← 从DIE_windows_x64_*_portable.zip解压得到
├── jadx/
│   ├── bin/
│   │   └── jadx.bat       ← 从jadx-*.zip解压得到
│   └── lib/
└── apktool/
    ├── apktool.bat
    └── apktool.jar
```

---

## ⚡ 快速验证

下载完成后，可以验证工具是否可用：

```powershell
# 测试 strings
.\tools\windows\strings\strings.exe --help

# 测试 UPX
.\tools\windows\upx\upx.exe -h

# 测试 DIE
.\tools\windows\die\diec.exe --help
```

---

## 🌐 国内加速镜像

使用以下镜像可显著加速下载：

| 镜像 | 用法 |
|------|------|
| ghproxy.com | `https://ghproxy.com/` + GitHub原始链接 |
| mirror.ghproxy.com | `https://mirror.ghproxy.com/` + GitHub原始链接 |
| gitee.com | 直接搜索国内镜像站 |

示例：
```
原始：https://github.com/upx/upx/releases/download/v4.2.4/upx-4.2.4-win64.zip
加速：https://ghproxy.com/https://github.com/upx/upx/releases/download/v4.2.4/upx-4.2.4-win64.zip
```
