# setup.py
import os
import sys
import platform
import shutil
import subprocess

ROOT = os.path.abspath(os.getcwd())
VENV_DIR = os.path.join(ROOT, "venv")

def run(cmd, **kwargs):
    """Helper to print and run shell commands safely."""
    print(f"\n$ {' '.join(map(str, cmd))}")
    subprocess.run(cmd, check=True, **kwargs)

def venv_python_path():
    """Return platform-specific path to the venv Python executable."""
    if platform.system().lower().startswith("win"):
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")

def run_npm_install(cwd):
    """Run npm install in a cross-platform safe way."""
    system = platform.system().lower()
    if system.startswith("win"):
        # 1️⃣ Try npm.cmd first (Windows uses this shim)
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if npm:
            return run([npm, "install"], cwd=cwd)

        # 2️⃣ Try the default Node.js installation path
        candidate = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "nodejs", "npm.cmd")
        if os.path.exists(candidate):
            return run([candidate, "install"], cwd=cwd)

        # 3️⃣ Fallback via cmd.exe path resolution
        return run(["cmd", "/c", "npm", "install"], cwd=cwd)
    else:
        # Unix / macOS
        npm = shutil.which("npm")
        if not npm:
            print("⚠️  package.json found but `npm` not detected in PATH. Skipping `npm install`.")
            return
        return run([npm, "install"], cwd=cwd)

def main():
    print("🔧 Setting up your environment...")

    # 1️⃣ Create virtual environment
    print("➡️  Creating virtual environment at ./venv")
    run([sys.executable, "-m", "venv", VENV_DIR])

    vpy = venv_python_path()
    if not os.path.exists(vpy):
        raise RuntimeError(f"Could not find venv python at: {vpy}")

    # 2️⃣ Upgrade pip
    print("➡️  Upgrading pip")
    run([vpy, "-m", "pip", "install", "--upgrade", "pip"])

    # 3️⃣ Install Python dependencies
    req = os.path.join(ROOT, "requirements.txt")
    if os.path.exists(req):
        print(f"➡️  Installing Python requirements from {req}")
        run([vpy, "-m", "pip", "install", "-r", req])
    else:
        print("ℹ️  No requirements.txt found; skipping Python dependency install.")

    # 4️⃣ Install Node.js dependencies (npm)
    pkg = os.path.join(ROOT, "package.json")
    if os.path.exists(pkg):
        print("➡️  Installing Node.js dependencies (npm install)")
        run_npm_install(ROOT)
    else:
        print("ℹ️  No package.json found; skipping npm install.")

    # 5️⃣ Finish up
    print("\n✅ Setup complete!")

    if platform.system().lower().startswith("win"):
        activate_path = os.path.join(VENV_DIR, "Scripts", "activate.bat")
        print("Launching a new PowerShell window with the virtual environment activated...")
        subprocess.run(["cmd", "/k", activate_path])
    else:
        print("Launching a new terminal with the virtual environment activated...")
        subprocess.run(["bash", "-c", f"source {VENV_DIR}/bin/activate && exec bash"])



if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ A command failed with exit code {e.returncode}. See output above.", file=sys.stderr)
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
