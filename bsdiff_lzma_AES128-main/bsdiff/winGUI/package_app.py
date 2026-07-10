import os
import subprocess
import sys
import shutil
import time
import random
import string

def generate_random_name(length=8):
    """Generate a random name for temporary executable file"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def package_application():
    """
    Package the bsdiff_gui_modern.py application into an executable using PyInstaller
    """
    print("Starting packaging process...")
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print("PyInstaller is already installed.")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Create spec file with custom settings
    random_name = generate_random_name()
    final_exe_name = 'BSDiff_GUI'
    temp_exe_name = f'temp_{random_name}'
    
    print(f"Using temporary name {temp_exe_name} for building...")
    
    spec_content = f"""
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Include bsdiff.exe
added_files = [
    ('../build/bin/bsdiff.exe', '.'),  # from bin/bsdiff.exe to root of distribution
]

a = Analysis(
    ['bsdiff_gui_modern.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
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
    name='{temp_exe_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)
    """
    
    # Create a simple app icon if it doesn't exist
    if not os.path.exists('app.ico'):
        try:
            from PIL import Image
            img = Image.new('RGB', (256, 256), color=(31, 119, 180))
            img.save('app_temp.png')
            
            # Convert PNG to ICO using PIL
            import PIL.Image
            img = PIL.Image.open('app_temp.png')
            img.save('app.ico')
            os.remove('app_temp.png')
            print("Created app.ico")
        except ImportError:
            print("PIL not found, skipping icon creation")
            # Update spec to not use an icon
            spec_content = spec_content.replace("icon='app.ico',", "")
    
    # Write the spec file
    with open('bsdiff_gui.spec', 'w') as f:
        f.write(spec_content.strip())
    
    print("Created spec file.")
    
    # Run PyInstaller
    print("Running PyInstaller...")
    try:
        subprocess.check_call([sys.executable, "-m", "PyInstaller", "bsdiff_gui.spec", "--clean"])
        
        # Prepare the dist directory
        dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
        temp_exe_path = os.path.join(dist_dir, f"{temp_exe_name}.exe")
        final_exe_path = os.path.join(dist_dir, f"{final_exe_name}.exe")
        
        # Remove the target file if it exists
        if os.path.exists(final_exe_path):
            try:
                os.remove(final_exe_path)
                print(f"Removed existing {final_exe_path}")
            except PermissionError:
                print(f"Could not remove {final_exe_path}, it's being used by another process.")
                print("Will try to use a different name.")
                final_exe_path = os.path.join(dist_dir, f"{final_exe_name}_{generate_random_name()}.exe")
        
        # Rename the temporary executable to the final name
        os.rename(temp_exe_path, final_exe_path)
        print(f"Renamed {temp_exe_path} to {final_exe_path}")
        
        print("Packaging complete!")
        print(f"Executable created at: {final_exe_path}")
        
        # Copy README.md and requirements.txt to the dist folder
        shutil.copy('README.md', os.path.join(dist_dir, 'README.md'))
        shutil.copy('requirements.txt', os.path.join(dist_dir, 'requirements.txt'))
        
        # Create a simple installation guide
        install_guide = """# BSDiff GUI Installation Guide

## Quick Start
1. Extract all files from the zip archive to a folder of your choice
2. Run BSDiff_GUI.exe

## Prerequisites
- Windows 10 or higher

## Troubleshooting
- If you get an error about missing DLLs, install the Visual C++ Redistributable

## Server Integration
To use the server integration features:
1. Make sure the server is running at the URL specified in the application
2. Provide a valid session cookie for authentication
3. Test the connection using the "Refresh Devices" button
"""
        
        with open(os.path.join(dist_dir, 'INSTALL.md'), 'w') as f:
            f.write(install_guide)
        
        print("Added documentation files to the dist folder")
        print(f"Installation guide created at: {os.path.join(dist_dir, 'INSTALL.md')}")
        
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: PyInstaller failed to create the executable: {e}")
        print("Please check the error message above for details.")

if __name__ == "__main__":
    package_application() 