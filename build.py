import os
import sys
import shutil
import platform
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("muselocal-build")

def get_target_triple() -> str:
    """
    Formulate the standard LLVM target triple for the host platform to match Tauri's naming conventions.
    """
    os_name = platform.system().lower()
    arch = platform.machine().lower()

    # Normalise CPU Architectures
    if arch in ["amd64", "x86_64", "x64"]:
        arch_norm = "x86_64"
    elif arch in ["arm64", "aarch64", "m1", "m2", "m3"]:
        arch_norm = "aarch64"
    else:
        arch_norm = arch

    # Format platform triples
    if os_name == "windows":
        return f"{arch_norm}-pc-windows-msvc"
    elif os_name == "darwin":
        return f"{arch_norm}-apple-darwin"
    elif os_name == "linux":
        return f"{arch_norm}-unknown-linux-gnu"
    else:
        return f"{arch_norm}-unknown-{os_name}"

def compile_sidecar():
    target_triple = get_target_triple()
    executable_name = f"server-{target_triple}"
    if platform.system().lower() == "windows":
        executable_name += ".exe"

    logger.info(f"Target system triple detected: {target_triple}")
    logger.info(f"Sidecar output binary name: {executable_name}")

    # Paths
    root_dir = os.path.dirname(os.path.abspath(__file__))
    entry_script = os.path.join(root_dir, "backend", "main.py")
    dist_dir = os.path.join(root_dir, "dist")
    binaries_dir = os.path.join(root_dir, "src-tauri", "binaries")

    # Command construction
    pyinstaller_cmd = [
        "pyinstaller",
        "--onefile",
        f"--name={executable_name.replace('.exe', '')}", # PyInstaller appends extension automatically on Windows
        "--clean",
        entry_script
    ]

    logger.info(f"Running PyInstaller command: {' '.join(pyinstaller_cmd)}")
    
    # Check if pyinstaller is available in path
    pyinstaller_path = shutil.which("pyinstaller")
    if not pyinstaller_path:
        logger.error("PyInstaller is not installed or not in PATH! Please install pyinstaller using pip first.")
        sys.exit(1)

    # Execute build
    result = subprocess.run(pyinstaller_cmd, cwd=root_dir)
    
    if result.returncode != 0:
        logger.error("Compilation failed!")
        sys.exit(result.returncode)

    # Ensure output binaries folder exists
    os.makedirs(binaries_dir, exist_ok=True)

    # Move binary to Tauri binaries folder
    source_bin = os.path.join(dist_dir, executable_name)
    dest_bin = os.path.join(binaries_dir, executable_name)

    logger.info(f"Moving compiled binary: {source_bin} -> {dest_bin}")
    if os.path.exists(dest_bin):
        os.remove(dest_bin)
    
    shutil.move(source_bin, dest_bin)
    logger.info("Sidecar compilation and installation completed successfully!")

if __name__ == "__main__":
    compile_sidecar()
