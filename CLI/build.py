#!/usr/bin/env python3
"""
Cross-platform build script for Melanie CLI.

Creates standalone executables for macOS, Linux, and Windows
using PyInstaller with proper configuration and optimization.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import platform


class CLIBuilder:
    """Builder for creating cross-platform CLI executables."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.build_dir = self.project_root / "build"
        self.dist_dir = self.project_root / "dist"
        self.spec_file = self.project_root / "melanie-cli.spec"
        
    def clean(self):
        """Clean previous build artifacts."""
        print("🧹 Cleaning previous build artifacts...")
        
        for dir_path in [self.build_dir, self.dist_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"   Removed {dir_path}")
        
        if self.spec_file.exists():
            self.spec_file.unlink()
            print(f"   Removed {self.spec_file}")
    
    def install_dependencies(self):
        """Install build dependencies."""
        print("📦 Installing dependencies...")
        
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True, cwd=self.project_root)
        
        print("   Dependencies installed successfully")
    
    def create_spec_file(self):
        """Create PyInstaller spec file with proper configuration."""
        print("📝 Creating PyInstaller spec file...")
        
        # Determine platform-specific settings
        system = platform.system().lower()
        
        if system == "darwin":  # macOS
            icon_file = "assets/melanie-cli.icns" if (self.project_root / "assets/melanie-cli.icns").exists() else None
            console = False  # Create app bundle
        elif system == "windows":
            icon_file = "assets/melanie-cli.ico" if (self.project_root / "assets/melanie-cli.ico").exists() else None
            console = True
        else:  # Linux and others
            icon_file = None
            console = True
        
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['{self.project_root}'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'aiohttp',
        'rich',
        'typer',
        'pydantic',
        'asyncio'
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='melanie-cli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console={str(console).lower()},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {'icon="' + icon_file + '",' if icon_file else ''}
)'''

        # Add macOS app bundle configuration
        if system == "darwin":
            spec_content += '''

app = BUNDLE(
    exe,
    name='Melanie CLI.app',
    icon='assets/melanie-cli.icns' if os.path.exists('assets/melanie-cli.icns') else None,
    bundle_identifier='com.melanie.cli',
    info_plist={{
        'CFBundleDisplayName': 'Melanie CLI',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
    }}
)'''
        
        with open(self.spec_file, 'w') as f:
            f.write(spec_content)
        
        print(f"   Created spec file: {self.spec_file}")
    
    def build_executable(self):
        """Build the executable using PyInstaller."""
        print("🔨 Building executable...")
        
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            str(self.spec_file)
        ]
        
        result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("❌ Build failed!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            sys.exit(1)
        
        print("   Build completed successfully")
    
    def create_distribution(self):
        """Create distribution package."""
        print("📦 Creating distribution package...")
        
        system = platform.system().lower()
        arch = platform.machine().lower()
        
        # Determine executable name and path
        if system == "darwin":
            if (self.dist_dir / "Melanie CLI.app").exists():
                executable_path = self.dist_dir / "Melanie CLI.app"
                package_name = f"melanie-cli-macos-{arch}.zip"
            else:
                executable_path = self.dist_dir / "melanie-cli"
                package_name = f"melanie-cli-macos-{arch}.tar.gz"
        elif system == "windows":
            executable_path = self.dist_dir / "melanie-cli.exe"
            package_name = f"melanie-cli-windows-{arch}.zip"
        else:
            executable_path = self.dist_dir / "melanie-cli"
            package_name = f"melanie-cli-linux-{arch}.tar.gz"
        
        if not executable_path.exists():
            print(f"❌ Executable not found: {executable_path}")
            sys.exit(1)
        
        # Create package
        package_path = self.project_root / package_name
        
        if system == "windows" or (system == "darwin" and package_name.endswith('.zip')):
            # Create ZIP archive
            shutil.make_archive(
                str(package_path.with_suffix('')),
                'zip',
                self.dist_dir,
                executable_path.name
            )
        else:
            # Create tar.gz archive
            shutil.make_archive(
                str(package_path.with_suffix('').with_suffix('')),
                'gztar',
                self.dist_dir,
                executable_path.name
            )
        
        print(f"   Created package: {package_name}")
        
        # Show file size
        if package_path.exists():
            size_mb = package_path.stat().st_size / (1024 * 1024)
            print(f"   Package size: {size_mb:.1f} MB")
    
    def verify_executable(self):
        """Verify the built executable works."""
        print("✅ Verifying executable...")
        
        system = platform.system().lower()
        
        if system == "darwin" and (self.dist_dir / "Melanie CLI.app").exists():
            executable_path = self.dist_dir / "Melanie CLI.app" / "Contents" / "MacOS" / "melanie-cli"
        else:
            executable_name = "melanie-cli.exe" if system == "windows" else "melanie-cli"
            executable_path = self.dist_dir / executable_name
        
        if not executable_path.exists():
            print(f"❌ Executable not found: {executable_path}")
            return False
        
        # Test version command
        try:
            result = subprocess.run([str(executable_path), "version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("   Executable verified successfully")
                return True
            else:
                print(f"   Executable test failed: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print("   Executable test timed out")
            return False
        except Exception as e:
            print(f"   Executable test error: {e}")
            return False
    
    def build(self, clean_first=True):
        """Run the complete build process."""
        print("🚀 Starting Melanie CLI build process...")
        print(f"   Platform: {platform.system()} {platform.machine()}")
        print(f"   Python: {sys.version}")
        
        try:
            if clean_first:
                self.clean()
            
            self.install_dependencies()
            self.create_spec_file()
            self.build_executable()
            
            if self.verify_executable():
                self.create_distribution()
                print("✨ Build completed successfully!")
            else:
                print("⚠️  Build completed but verification failed")
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Build failed: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)


def main():
    """Main entry point for build script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build Melanie CLI executable")
    parser.add_argument("--no-clean", action="store_true", 
                       help="Don't clean previous build artifacts")
    parser.add_argument("--verify-only", action="store_true",
                       help="Only verify existing executable")
    
    args = parser.parse_args()
    
    builder = CLIBuilder()
    
    if args.verify_only:
        builder.verify_executable()
    else:
        builder.build(clean_first=not args.no_clean)


if __name__ == "__main__":
    main()