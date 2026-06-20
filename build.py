"""
打包脚本
使用 PyInstaller 打包为独立可执行文件
支持 Windows (.exe) 和 Linux (ELF)
"""
import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path


class Builder:
    """构建器"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.src_dir = self.project_root / "src"
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build"
        self.is_windows = sys.platform == "win32"
        self.spec_file = self.project_root / "AI-RE-Toolkit.spec"

    def clean(self):
        """清理构建产物"""
        print("[1/5] 清理旧构建产物...")
        for d in [self.dist_dir, self.build_dir]:
            if d.exists():
                shutil.rmtree(d)
                print(f"  已删除: {d}")

        # 删除旧的spec文件
        if self.spec_file.exists():
            self.spec_file.unlink()
            print(f"  已删除: {self.spec_file}")

    def generate_spec(self):
        """生成 PyInstaller spec 文件"""
        print("[2/5] 生成打包配置...")

        # 收集需要包含的数据文件
        data_files = [
            ("config", "config"),
            ("src/ai/prompts", "src/ai/prompts"),
            ("src/tools/definitions", "src/tools/definitions"),
            ("resources", "resources"),
        ]

        # 构建 --add-data 参数
        separator = ";" if self.is_windows else ":"
        add_data_args = []
        for src, dst in data_files:
            src_path = self.project_root / src
            if src_path.exists():
                add_data_args.append(f"--add-data={src}{separator}{dst}")

        # 工具目录（如果有预编译工具）
        tools_dir = self.project_root / "tools"
        if tools_dir.exists() and any(tools_dir.iterdir()):
            add_data_args.append(f"--add-data=tools{separator}tools")

        # 隐藏导入
        hidden_imports = [
            "src.core.file_analyzer",
            "src.core.binary_reader",
            "src.ai.providers.ollama_provider",
            "src.ai.providers.openai_provider",
            "src.tools.registry",
            "src.tools.executor",
            "src.utils.logger",
            "requests",
        ]

        hidden_args = [f"--hidden-import={imp}" for imp in hidden_imports]

        # 图标
        icon_arg = ""
        icon_path = self.project_root / "resources" / "icons" / "icon.ico"
        if icon_path.exists() and self.is_windows:
            icon_arg = f"--icon={icon_path}"

        # 生成spec文件内容
        spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src/main.py'],
    pathex=[r'{self.project_root}'],
    binaries=[],
    datas={add_data_args},
    hiddenimports={hidden_imports},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AI-RE-Toolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {icon_arg and f"icon='{icon_path}',"}
)
"""
        with open(self.spec_file, "w", encoding="utf-8") as f:
            f.write(spec_content)

        print(f"  已生成: {self.spec_file}")

    def build(self):
        """执行打包"""
        print("[3/5] 开始打包...")

        cmd = [
            sys.executable, "-m", "PyInstaller",
            str(self.spec_file),
            "--clean",
            "--noconfirm",
        ]

        # Windows 单文件模式（可选）
        # cmd.append("--onefile")

        # 使用目录模式（启动更快，适合大文件）
        cmd.append("--onedir")

        print(f"  执行: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=self.project_root)

        if result.returncode != 0:
            print("[错误] 打包失败")
            return False

        print("  打包成功")
        return True

    def post_process(self):
        """后处理"""
        print("[4/5] 后处理...")

        dist_path = self.dist_dir / "AI-RE-Toolkit"

        if not dist_path.exists():
            print(f"[警告] 输出目录不存在: {dist_path}")
            return

        # 复制额外文件
        extras = [
            ("README.md", "README.md"),
            ("LICENSE", "LICENSE"),
        ]

        for src, dst in extras:
            src_path = self.project_root / src
            if src_path.exists():
                shutil.copy2(src_path, dist_path / dst)
                print(f"  已复制: {src} -> {dst}")

        # 创建启动脚本（Linux）
        if not self.is_windows:
            launcher = dist_path / "run.sh"
            with open(launcher, "w") as f:
                f.write("#!/bin/bash\\n")
                f.write("cd \"$(dirname \"$0\")\"\\n")
                f.write("./AI-RE-Toolkit\\n")
            os.chmod(launcher, 0o755)
            print(f"  已创建: {launcher}")

        print(f"  输出目录: {dist_path}")

    def verify(self):
        """验证构建结果"""
        print("[5/5] 验证...")

        dist_path = self.dist_dir / "AI-RE-Toolkit"
        exe_name = "AI-RE-Toolkit.exe" if self.is_windows else "AI-RE-Toolkit"
        exe_path = dist_path / exe_name

        if exe_path.exists():
            size = exe_path.stat().st_size
            print(f"  可执行文件: {exe_path}")
            print(f"  文件大小: {size / 1024 / 1024:.1f} MB")
            print("[成功] 构建完成!")
            return True
        else:
            print(f"[错误] 可执行文件未找到: {exe_path}")
            return False

    def run(self):
        """执行完整构建流程"""
        print("=" * 50)
        print("AI-RE Toolkit 打包脚本")
        print(f"平台: {platform.system()}")
        print(f"项目目录: {self.project_root}")
        print("=" * 50)

        self.clean()
        self.generate_spec()

        if not self.build():
            return False

        self.post_process()
        return self.verify()


def quick_build():
    """快速打包（使用命令行参数）"""
    builder = Builder()

    # 解析参数
    if "--clean" in sys.argv:
        builder.clean()

    if "--spec-only" in sys.argv:
        builder.generate_spec()
        return

    builder.run()


if __name__ == "__main__":
    quick_build()
