#!/usr/bin/env python3
"""
MindGraph Dependency Checker - GUI Version

A graphical interface for checking and installing dependencies.
"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
import requests

class DependencyCheckerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MindGraph Dependency Checker")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        # Variables
        self.python_ok = False
        self.nodejs_ok = False
        self.d3js_ok = False
        self.playwright_ok = False
        
        self.setup_ui()
        self.run_checks()
    
    def setup_ui(self):
        """Setup the user interface."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="MindGraph Dependency Checker", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Dependency Status", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Python status
        self.python_status = ttk.Label(status_frame, text="🔍 Checking Python packages...")
        self.python_status.grid(row=0, column=0, sticky=tk.W, pady=2)
        
        # Node.js status
        self.nodejs_status = ttk.Label(status_frame, text="🔍 Checking Node.js...")
        self.nodejs_status.grid(row=1, column=0, sticky=tk.W, pady=2)
        
        # D3.js status
        self.d3js_status = ttk.Label(status_frame, text="🔍 Checking D3.js dependencies...")
        self.d3js_status.grid(row=2, column=0, sticky=tk.W, pady=2)
        
        # Playwright status
        self.playwright_status = ttk.Label(status_frame, text="🔍 Checking Playwright browsers...")
        self.playwright_status.grid(row=3, column=0, sticky=tk.W, pady=2)
        
        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Installation Log", padding="5")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=70)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        
        # Install buttons - Simplified to just "Install All Missing"
        self.install_all_btn = ttk.Button(button_frame, text="Install All Missing Dependencies", 
                                         command=self.install_all, state=tk.DISABLED)
        self.install_all_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Keep individual buttons but hide them initially (for advanced users)
        self.install_python_btn = ttk.Button(button_frame, text="Install Python Packages", 
                                           command=self.install_python, state=tk.DISABLED)
        # self.install_python_btn.pack(side=tk.LEFT, padx=(0, 5))  # Hidden
        
        self.install_d3js_btn = ttk.Button(button_frame, text="Install D3.js Dependencies", 
                                          command=self.install_d3js, state=tk.DISABLED)
        # self.install_d3js_btn.pack(side=tk.LEFT, padx=(0, 5))  # Hidden
        
        self.install_playwright_btn = ttk.Button(button_frame, text="Install Playwright Chrome", 
                                               command=self.install_playwright, state=tk.DISABLED)
        # self.install_playwright_btn.pack(side=tk.LEFT, padx=(0, 5))  # Hidden
        
        self.install_nodejs_btn = ttk.Button(button_frame, text="Install Node.js", 
                                           command=self.install_nodejs, state=tk.DISABLED)
        # self.install_nodejs_btn.pack(side=tk.LEFT, padx=(0, 5))  # Hidden
        
        self.show_nodejs_guide_btn = ttk.Button(button_frame, text="Node.js Guide", 
                                              command=self.show_nodejs_guide, state=tk.DISABLED)
        # self.show_nodejs_guide_btn.pack(side=tk.LEFT, padx=(0, 5))  # Hidden
        
        self.start_app_btn = ttk.Button(button_frame, text="Start", 
                                       command=self.start_application_and_load_webpage, state=tk.DISABLED)
        self.start_app_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Removed the separate Load Webpage button
        # self.load_webpage_btn = ttk.Button(button_frame, text="Load Webpage", 
        #                                   command=self.load_webpage)
        # self.load_webpage_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(button_frame, text="Exit", command=self.root.quit).pack(side=tk.LEFT)
    
    def log(self, message):
        """Add message to log area."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def run_checks(self):
        """Run dependency checks in a separate thread."""
        def check_thread():
            self.log("🚀 Starting dependency checks...\n")
            
            # Check Python packages
            self.log("🔍 Checking Python packages...")
            self.python_ok = self.check_python_packages()
            
            # Check Node.js
            self.log("\n🔍 Checking Node.js installation...")
            self.nodejs_ok = self.check_nodejs_installation()
            
            # Check D3.js
            self.log("\n🔍 Checking D3.js dependencies...")
            self.d3js_ok = self.check_d3js_dependencies()
            
            # Check Playwright browsers
            self.log("\n🔍 Checking Playwright browsers...")
            self.playwright_ok = self.check_playwright_browsers()
            
            # Update UI
            self.root.after(0, self.update_ui_after_checks)
        
        threading.Thread(target=check_thread, daemon=True).start()
    
    def check_python_packages(self):
        """Check Python packages."""
        required_packages = [
            'flask', 'requests', 'langchain', 'yaml', 'dotenv', 
            'nest_asyncio', 'pyee', 'websockets', 'playwright',
            'werkzeug', 'PIL', 'flask_limiter', 'flask_cors'
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                if package == 'yaml':
                    import yaml
                elif package == 'dotenv':
                    import dotenv
                elif package == 'PIL':
                    import PIL
                elif package == 'flask_limiter':
                    import flask_limiter
                elif package == 'flask_cors':
                    import flask_cors
                else:
                    __import__(package)
                self.log(f"✅ {package}")
            except ImportError:
                missing_packages.append(package)
                self.log(f"❌ {package} - NOT INSTALLED")
        
        if missing_packages:
            self.log(f"\n❌ Missing Python packages: {', '.join(missing_packages)}")
            return False
        
        self.log("✅ All Python packages are installed!")
        return True
    
    def check_nodejs_installation(self):
        """Check Node.js installation."""
        # Check Node.js
        try:
            node_version = subprocess.run(['node', '--version'], 
                                        capture_output=True, text=True, check=True)
            self.log(f"✅ Node.js {node_version.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log("❌ Node.js is not installed or not in PATH")
            return False
        
        # Check npm
        npm_found = False
        try:
            result = subprocess.run(['npm', '--version'], 
                                  capture_output=True, text=True, check=True)
            self.log(f"✅ npm {result.stdout.strip()}")
            npm_found = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        if not npm_found:
            try:
                result = subprocess.run('npm --version', 
                                      shell=True, capture_output=True, text=True, check=True)
                self.log(f"✅ npm {result.stdout.strip()}")
                npm_found = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        
        if not npm_found:
            self.log("❌ npm is not installed or not in PATH")
            return False
        
        return True
    
    def check_d3js_dependencies(self):
        """Check D3.js dependencies."""
        d3js_dir = Path(__file__).parent.parent / 'd3.js'
        
        if not d3js_dir.exists():
            self.log(f"❌ D3.js directory not found: {d3js_dir}")
            return False
        
        package_json = d3js_dir / 'package.json'
        if not package_json.exists():
            self.log(f"❌ package.json not found in D3.js directory")
            return False
        
        node_modules = d3js_dir / 'node_modules'
        if not node_modules.exists():
            self.log("❌ node_modules directory not found in D3.js directory")
            return False
        
        key_dependencies = [
            'd3-array', 'd3-axis', 'd3-scale', 'd3-selection', 
            'd3-shape', 'd3-color', 'd3-format'
        ]
        
        missing_deps = []
        for dep in key_dependencies:
            dep_path = node_modules / dep
            if dep_path.exists():
                self.log(f"✅ {dep}")
            else:
                missing_deps.append(dep)
                self.log(f"❌ {dep} - NOT INSTALLED")
        
        if missing_deps:
            self.log(f"\n❌ Missing D3.js dependencies: {', '.join(missing_deps)}")
            return False
        
        self.log("✅ All D3.js dependencies are installed!")
        return True
    
    def check_playwright_browsers(self):
        """Check Playwright browsers."""
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                # Try to launch Chrome to check if it's installed
                try:
                    browser = p.chromium.launch(headless=True)
                    browser.close()
                    self.log("✅ Playwright Chrome browser is installed")
                    return True
                except Exception as e:
                    self.log(f"❌ Playwright Chrome browser is not installed: {e}")
                    return False
        except ImportError:
            self.log("❌ Playwright package is not installed")
            return False
    
    def update_ui_after_checks(self):
        """Update UI after checks are complete."""
        # Update status labels
        if self.python_ok:
            self.python_status.config(text="✅ Python packages: OK", foreground="green")
        else:
            self.python_status.config(text="❌ Python packages: Missing", foreground="red")
        
        if self.nodejs_ok:
            self.nodejs_status.config(text="✅ Node.js/npm: OK", foreground="green")
        else:
            self.nodejs_status.config(text="❌ Node.js/npm: Missing", foreground="red")
        
        if self.d3js_ok:
            self.d3js_status.config(text="✅ D3.js dependencies: OK", foreground="green")
        else:
            self.d3js_status.config(text="❌ D3.js dependencies: Missing", foreground="red")
        
        if self.playwright_ok:
            self.playwright_status.config(text="✅ Playwright Chrome browser: OK", foreground="green")
        else:
            self.playwright_status.config(text="❌ Playwright Chrome browser: Missing", foreground="red")
        
        # Update buttons - Simplified to just show "Install All Missing" or "Start Application"
        if not (self.python_ok and self.nodejs_ok and self.d3js_ok and self.playwright_ok):
            self.install_all_btn.config(state=tk.NORMAL)
            self.log("\n⚠️  Missing dependencies detected. Click 'Install All Missing Dependencies' to install them.")
        else:
            self.start_app_btn.config(state=tk.NORMAL)
            self.log("\n🎉 All dependencies are installed! You can start the application.")
    
    def install_python(self):
        """Install Python packages."""
        def install_thread():
            self.log("\n🔧 Installing Python packages...")
            try:
                result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                                      capture_output=True, text=True, check=True)
                self.log("✅ Python packages installed successfully!")
                self.root.after(0, lambda: self.install_python_btn.config(state=tk.DISABLED))
                self.root.after(0, lambda: self.python_status.config(text="✅ Python packages: OK", foreground="green"))
                self.python_ok = True
            except subprocess.CalledProcessError as e:
                self.log(f"❌ Failed to install Python packages: {e.stderr}")
        
        threading.Thread(target=install_thread, daemon=True).start()
    
    def install_d3js(self):
        """Install D3.js dependencies."""
        def install_thread():
            self.log("\n🔧 Installing D3.js dependencies...")
            d3js_dir = Path(__file__).parent.parent / 'd3.js'
            try:
                result = subprocess.run(['npm', 'install'], 
                                      cwd=d3js_dir, capture_output=True, text=True, check=True)
                self.log("✅ D3.js dependencies installed successfully!")
                self.root.after(0, lambda: self.install_d3js_btn.config(state=tk.DISABLED))
                self.root.after(0, lambda: self.d3js_status.config(text="✅ D3.js dependencies: OK", foreground="green"))
                self.d3js_ok = True
            except subprocess.CalledProcessError as e:
                self.log(f"❌ Failed to install D3.js dependencies: {e.stderr}")
        
        threading.Thread(target=install_thread, daemon=True).start()
    
    def install_playwright(self):
        """Install Playwright Chrome browser."""
        def install_thread():
            self.log("\n🔧 Installing Playwright Chrome browser...")
            try:
                result = subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], 
                                      capture_output=True, text=True, check=True)
                self.log("✅ Playwright Chrome browser installed successfully!")
                self.root.after(0, lambda: self.playwright_status.config(text="✅ Playwright Chrome browser: OK", foreground="green"))
                self.playwright_ok = True
            except subprocess.CalledProcessError as e:
                self.log(f"❌ Failed to install Playwright Chrome browser: {e.stderr}")
        
        threading.Thread(target=install_thread, daemon=True).start()
    
    def install_nodejs(self):
        """Install Node.js automatically."""
        def install_thread():
            self.log("\n🔧 Attempting automatic Node.js installation...")
            platform = sys.platform.lower()
            
            try:
                if platform.startswith('win'):
                    # Windows - try winget first, then chocolatey
                    self.log("🪟 Detected Windows - attempting automatic installation...")
                    
                    # Try winget (Windows 10/11)
                    try:
                        self.log("Trying winget installation...")
                        result = subprocess.run(['winget', 'install', 'OpenJS.NodeJS'], 
                                              capture_output=True, text=True, check=True)
                        self.log("✅ Node.js installed successfully via winget!")
                        self.log("Please restart your terminal and run the dependency checker again.")
                        self.root.after(0, lambda: messagebox.showinfo("Success", 
                            "Node.js installed successfully!\n\nPlease restart your terminal and run the dependency checker again."))
                        return
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        self.log("Winget not available, trying Chocolatey...")
                        
                        # Try chocolatey
                        try:
                            result = subprocess.run(['choco', 'install', 'nodejs', '-y'], 
                                                  capture_output=True, text=True, check=True)
                            self.log("✅ Node.js installed successfully via Chocolatey!")
                            self.log("Please restart your terminal and run the dependency checker again.")
                            self.root.after(0, lambda: messagebox.showinfo("Success", 
                                "Node.js installed successfully!\n\nPlease restart your terminal and run the dependency checker again."))
                            return
                        except (subprocess.CalledProcessError, FileNotFoundError):
                            self.log("Chocolatey not available.")
                    
                elif platform.startswith('darwin'):
                    # macOS - try Homebrew
                    self.log("🍎 Detected macOS - attempting Homebrew installation...")
                    try:
                        result = subprocess.run(['brew', 'install', 'node'], 
                                              capture_output=True, text=True, check=True)
                        self.log("✅ Node.js installed successfully via Homebrew!")
                        self.log("Please restart your terminal and run the dependency checker again.")
                        self.root.after(0, lambda: messagebox.showinfo("Success", 
                            "Node.js installed successfully!\n\nPlease restart your terminal and run the dependency checker again."))
                        return
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        self.log("Homebrew not available.")
                
                elif platform.startswith('linux'):
                    # Linux - try package manager
                    self.log("🐧 Detected Linux - attempting package manager installation...")
                    
                    # Try apt (Ubuntu/Debian)
                    try:
                        self.log("Trying apt installation...")
                        # Add NodeSource repository
                        subprocess.run(['curl', '-fsSL', 'https://deb.nodesource.com/setup_lts.x'], 
                                     capture_output=True, text=True, check=True)
                        result = subprocess.run(['sudo', 'apt-get', 'install', '-y', 'nodejs'], 
                                              capture_output=True, text=True, check=True)
                        self.log("✅ Node.js installed successfully via apt!")
                        self.log("Please restart your terminal and run the dependency checker again.")
                        self.root.after(0, lambda: messagebox.showinfo("Success", 
                            "Node.js installed successfully!\n\nPlease restart your terminal and run the dependency checker again."))
                        return
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        self.log("apt not available or failed.")
                
                self.log("❌ Automatic installation not available for this platform.")
                self.log("Please install Node.js manually using the guide.")
                self.root.after(0, lambda: messagebox.showwarning("Manual Installation Required", 
                    "Automatic Node.js installation is not available for this platform.\n\n"
                    "Please use the 'Node.js Guide' button to see manual installation instructions."))
                
            except Exception as e:
                self.log(f"❌ Automatic installation failed: {e}")
                self.log("Please install Node.js manually using the guide.")
                self.root.after(0, lambda: messagebox.showerror("Installation Failed", 
                    f"Automatic Node.js installation failed: {e}\n\n"
                    "Please use the 'Node.js Guide' button to see manual installation instructions."))
        
        threading.Thread(target=install_thread, daemon=True).start()
    
    def show_nodejs_guide(self):
        """Show Node.js installation guide."""
        guide_text = """
📥 NODE.JS INSTALLATION GUIDE

Node.js is required for running D3.js dependencies. Here are installation options:

🖥️ WINDOWS INSTALLATION:

Option 1: Download from Official Website (Recommended)
1. Visit: https://nodejs.org/
2. Download the LTS version (Recommended for most users)
3. Run the installer (.msi file)
4. Follow the installation wizard
5. Restart your terminal/command prompt

Option 2: Using Chocolatey (if installed)
   choco install nodejs

Option 3: Using Winget (Windows 10/11)
   winget install OpenJS.NodeJS

Option 4: Using Scoop (if installed)
   scoop install nodejs

🍎 macOS INSTALLATION:

Option 1: Download from Official Website
1. Visit: https://nodejs.org/
2. Download the macOS installer (.pkg file)
3. Run the installer and follow the instructions

Option 2: Using Homebrew (Recommended)
   brew install node

Option 3: Using MacPorts
   sudo port install nodejs

🐧 LINUX INSTALLATION:

Ubuntu/Debian:
   curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
   sudo apt-get install -y nodejs

CentOS/RHEL/Fedora:
   curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -
   sudo yum install -y nodejs

Arch Linux:
   sudo pacman -S nodejs npm

📋 VERIFICATION:

After installation, verify Node.js is installed:
   node --version
   npm --version

Both commands should return version numbers.

🔄 RESTART REQUIRED:

After installing Node.js, you may need to:
1. Close and reopen your terminal/command prompt
2. Restart your IDE/editor
3. Run the dependency checker again
"""
        
        # Create a new window for the guide
        guide_window = tk.Toplevel(self.root)
        guide_window.title("Node.js Installation Guide")
        guide_window.geometry("700x600")
        guide_window.resizable(True, True)
        
        # Add scrollable text widget
        text_widget = scrolledtext.ScrolledText(guide_window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Insert the guide text
        text_widget.insert(tk.END, guide_text)
        text_widget.config(state=tk.DISABLED)  # Make it read-only
        
        # Add close button
        close_btn = ttk.Button(guide_window, text="Close", command=guide_window.destroy)
        close_btn.pack(pady=(0, 10))
    
    def install_all(self):
        """Install all missing dependencies."""
        if not self.python_ok:
            self.install_python()
        if not self.d3js_ok:
            self.install_d3js()
        if not self.playwright_ok:
            self.install_playwright()
        if not self.nodejs_ok:
            self.log("\n🔧 Attempting to install Node.js automatically...")
            self.install_nodejs()
    
    def is_server_running(self):
        """Check if the server is already running."""
        try:
            response = requests.get("http://localhost:9527", timeout=2)
            return True
        except:
            return False

    def start_application_and_load_webpage(self):
        """Start the main application and load the webpage."""
        # Check if server is already running
        if self.is_server_running():
            self.log("✅ Server is already running!")
            self.load_webpage()
            messagebox.showinfo("Server Running", "MindGraph application is already running!\nThe webpage will be opened in your browser.")
            return
        
        self.log("\n🚀 Starting MindGraph application...")
        
        # Disable the start button to prevent multiple clicks
        self.start_app_btn.config(state=tk.DISABLED)
        self.start_app_btn.config(text="Starting...")
        
        try:
            # Start the application in a separate process
            process = subprocess.Popen([sys.executable, Path(__file__).parent.parent / 'app.py'])
            self.log("✅ Application process started successfully!")
            
            # Start checking if the server is ready
            self.check_server_ready(process)
            
        except Exception as e:
            self.log(f"❌ Failed to start application: {e}")
            messagebox.showerror("Error", f"Failed to start application: {e}")
            # Re-enable the button on error
            self.start_app_btn.config(state=tk.NORMAL)
            self.start_app_btn.config(text="Start")

    def check_server_ready(self, process):
        """Check if the server is ready and then open the webpage."""
        import requests
        import time
        
        # Add a timeout counter to prevent infinite waiting
        timeout_counter = 0
        max_timeout = 30  # Maximum 30 seconds to wait
        
        def check_ready():
            nonlocal timeout_counter
            timeout_counter += 1
            
            try:
                # Try to connect to the server
                response = requests.get("http://localhost:9527", timeout=2)
                if response.status_code == 200:
                    self.log("✅ Server is ready!")
                    # Open the webpage
                    self.load_webpage()
                    # Re-enable the button
                    self.start_app_btn.config(state=tk.NORMAL)
                    self.start_app_btn.config(text="Start")
                    messagebox.showinfo("Success", "MindGraph application is running!\nThe webpage has been opened in your browser.")
                else:
                    # Server responded but with an error status, still consider it ready
                    self.log("✅ Server is ready!")
                    self.load_webpage()
                    self.start_app_btn.config(state=tk.NORMAL)
                    self.start_app_btn.config(text="Start")
                    messagebox.showinfo("Success", "MindGraph application is running!\nThe webpage has been opened in your browser.")
            except requests.exceptions.ConnectionError:
                # Server not ready yet, check again in 1 second
                if timeout_counter < max_timeout:
                    self.log(f"⏳ Waiting for server to start... ({timeout_counter}/{max_timeout})")
                    self.root.after(1000, check_ready)
                else:
                    self.log("❌ Server failed to start within timeout period")
                    self.log("💡 The application may still be starting. You can manually open: http://localhost:9527")
                    # Re-enable the button
                    self.start_app_btn.config(state=tk.NORMAL)
                    self.start_app_btn.config(text="Start")
                    messagebox.showwarning("Timeout", 
                        "Server did not start within the expected time.\n\n"
                        "The application may still be starting. You can manually open:\n"
                        "http://localhost:9527")
            except requests.exceptions.Timeout:
                # Timeout, check again in 1 second
                if timeout_counter < max_timeout:
                    self.log(f"⏳ Waiting for server to start... ({timeout_counter}/{max_timeout})")
                    self.root.after(1000, check_ready)
                else:
                    self.log("❌ Server failed to start within timeout period")
                    self.log("💡 The application may still be starting. You can manually open: http://localhost:9527")
                    # Re-enable the button
                    self.start_app_btn.config(state=tk.NORMAL)
                    self.start_app_btn.config(text="Start")
                    messagebox.showwarning("Timeout", 
                        "Server did not start within the expected time.\n\n"
                        "The application may still be starting. You can manually open:\n"
                        "http://localhost:9527")
            except Exception as e:
                self.log(f"❌ Error checking server status: {e}")
                # Re-enable the button on error
                self.start_app_btn.config(state=tk.NORMAL)
                self.start_app_btn.config(text="Start")
                messagebox.showerror("Error", f"Error checking server status: {e}")
        
        # Start checking after a short delay
        self.root.after(2000, check_ready)

    def load_webpage(self):
        """Open the application webpage in the default browser."""
        import webbrowser
        url = "http://localhost:9527"
        self.log(f"🌐 Opening webpage: {url}")
        try:
            webbrowser.open(url)
            self.log("✅ Webpage opened successfully!")
        except Exception as e:
            self.log(f"❌ Failed to open webpage: {e}")
            messagebox.showerror("Error", f"Failed to open webpage: {e}")

def main():
    """Main function."""
    root = tk.Tk()
    app = DependencyCheckerGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main() 