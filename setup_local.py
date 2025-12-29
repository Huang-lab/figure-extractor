import os
import subprocess
import sys
from pathlib import Path
import urllib.request

def check_java():
    """Check if Java is installed."""
    try:
        result = subprocess.run(['java', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Java is installed.")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ Java is not installed.")
    if sys.platform == "darwin":
        print("💡 On macOS, you can install it using Homebrew:")
        print("   brew install openjdk@11")
        print("   sudo ln -sfn $(brew --prefix)/opt/openjdk@11/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk-11.jdk")
    elif sys.platform == "linux":
        print("💡 On Ubuntu/Debian, you can install it using:")
        print("   sudo apt update && sudo apt install default-jdk")
    
    return False

def check_sbt():
    """Check if sbt is installed."""
    try:
        result = subprocess.run(['sbt', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ sbt is installed.")
            return True
    except FileNotFoundError:
        pass
    
    print("⚠️ sbt is not installed.")
    if sys.platform == "darwin":
        print("💡 On macOS, you can install it using Homebrew:")
        print("   brew install sbt")
    elif sys.platform == "linux":
        print("💡 On Ubuntu/Debian, you can install it using:")
        print("   echo \"deb https://repo.scala-sbt.org/scalasbt/debian all main\" | sudo tee /etc/apt/sources.list.d/sbt.list")
        print("   curl -sL \"https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x99E82A75642AC823\" | sudo apt-key add")
        print("   sudo apt update && sudo apt install sbt")
    
    return False

def setup_pdffigures2():
    """Clone and build pdffigures2."""
    base_dir = Path(__file__).resolve().parent
    pdffigures_dir = base_dir / 'pdffigures2'
    jar_path = pdffigures_dir / 'pdffigures2.jar'

    if jar_path.exists():
        print(f"✅ pdffigures2.jar already exists at {jar_path}")
        return True

    if not pdffigures_dir.exists():
        print("Cloning pdffigures2...")
        subprocess.run(['git', 'clone', 'https://github.com/allenai/pdffigures2.git', str(pdffigures_dir)], check=True)
    
    if check_sbt():
        print("Building pdffigures2 with sbt...")
        env = os.environ.copy()
        
        # On macOS, try to find Java 11 specifically as pdffigures2 requires it
        if sys.platform == "darwin":
            try:
                java_home = subprocess.check_output(['/usr/libexec/java_home', '-v', '11'], text=True).strip()
                env['JAVA_HOME'] = java_home
                print(f"Using JAVA_HOME: {java_home}")
            except subprocess.CalledProcessError:
                print("⚠️ Java 11 not found via java_home. Build might fail if default Java is too new.")

        try:
            subprocess.run(['sbt', 'assembly'], cwd=str(pdffigures_dir), env=env, check=True)
            
            # Check if it was built to the root (as per some build.sbt versions)
            if jar_path.exists():
                print(f"✅ Successfully built JAR at {jar_path}")
                return True
                
            # Otherwise look in target directories
            for scala_ver in ['scala-2.12', 'scala-2.11']:
                target_dir = pdffigures_dir / 'target' / scala_ver
                jars = list(target_dir.glob('pdffigures2-assembly-*.jar'))
                if jars:
                    import shutil
                    shutil.copy(jars[0], jar_path)
                    print(f"✅ Successfully built and moved JAR to {jar_path}")
                    return True
            
            print("❌ Build succeeded but could not find the resulting JAR file.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to build pdffigures2: {e}")
    else:
        print("❌ Cannot build pdffigures2 without sbt.")
        print("Please install sbt or manually provide pdffigures2.jar in the pdffigures2/ directory.")
    
    return False

def install_requirements():
    """Install Python requirements."""
    print("Installing Python requirements...")
    
    # Check if we are in a venv
    in_venv = os.environ.get('VIRTUAL_ENV') is not None
    
    cmd = [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt']
    
    # If not in venv and on macOS/Linux, we might need --break-system-packages
    if not in_venv and sys.platform != "win32":
        cmd.append('--break-system-packages')
        
    try:
        subprocess.run(cmd, check=True)
        print("✅ Python requirements installed.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        print("💡 Try creating a virtual environment first:")
        print("   python3 -m venv venv")
        print("   source venv/bin/activate")
        print("   python3 setup_local.py")
        return False

def main():
    print("🚀 Setting up Figure Extractor for local run...")
    
    if not check_java():
        sys.exit(1)
        
    if not setup_pdffigures2():
        print("⚠️ pdffigures2 setup failed. You might need to build it manually.")
        
    if not install_requirements():
        sys.exit(1)
        
    print("\n✨ Setup complete! You can now run the extractor locally.")
    print("To run the CLI: python figure_extractor.py <pdf_file> --local")
    print("To run the API: python run.py")

if __name__ == "__main__":
    main()
