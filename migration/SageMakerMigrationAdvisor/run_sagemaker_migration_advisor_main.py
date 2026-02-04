#!/usr/bin/env python3
"""
SageMaker Migration Advisor - Main Launcher
Provides a dropdown menu to select between Lite and Regular modes
"""

import sys
import subprocess
import threading
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    print("Warning: tkinter not available. Falling back to CLI mode.")


class MigrationAdvisorLauncher:
    """GUI launcher for SageMaker Migration Advisor"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SageMaker Migration Advisor Launcher")
        self.root.geometry("650x550")  # Increased height to ensure buttons are visible
        self.root.resizable(False, False)
        
        # Track launch button for state management
        self.launch_button = None
        
        # Center window on screen
        self.center_window()
        
        # Configure style
        self.setup_styles()
        
        # Create UI
        self.create_widgets()
        
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def setup_styles(self):
        """Setup custom styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('Title.TLabel', 
                       font=('Helvetica', 18, 'bold'),
                       foreground='#2E86AB',
                       padding=10)
        
        style.configure('Subtitle.TLabel',
                       font=('Helvetica', 11),
                       foreground='#555555',
                       padding=5)
        
        style.configure('Option.TLabel',
                       font=('Helvetica', 10, 'bold'),
                       foreground='#333333',
                       padding=5)
        
        style.configure('Description.TLabel',
                       font=('Helvetica', 9),
                       foreground='#666666',
                       wraplength=500,
                       justify='left')
        
        style.configure('Launch.TButton',
                       font=('Helvetica', 12, 'bold'),
                       padding=10)
    
    def create_widgets(self):
        """Create UI widgets"""
        # Main container - don't expand
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=False)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="🚀 SageMaker Migration Advisor",
            style='Title.TLabel'
        )
        title_label.pack(pady=(0, 5))
        
        # Subtitle
        subtitle_label = ttk.Label(
            main_frame,
            text="Select your migration advisor mode",
            style='Subtitle.TLabel'
        )
        subtitle_label.pack(pady=(0, 10))
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=5)
        
        # Mode selection label
        mode_label = ttk.Label(
            main_frame,
            text="Choose Migration Mode:",
            style='Option.TLabel'
        )
        mode_label.pack(anchor='w', pady=(5, 5))
        
        # Dropdown for mode selection
        self.mode_var = tk.StringVar(value="Migration Advisor Lite")
        mode_options = [
            "Migration Advisor Lite",
            "Migration Advisor Regular"
        ]
        
        self.mode_dropdown = ttk.Combobox(
            main_frame,
            textvariable=self.mode_var,
            values=mode_options,
            state='readonly',
            font=('Helvetica', 11),
            width=40
        )
        self.mode_dropdown.pack(pady=5)
        self.mode_dropdown.bind('<<ComboboxSelected>>', self.on_mode_change)
        
        # Description frame - fixed height
        desc_frame = ttk.LabelFrame(
            main_frame,
            text="Mode Description",
            padding="10"
        )
        desc_frame.pack(fill='x', pady=10)
        desc_frame.configure(height=200)
        desc_frame.pack_propagate(False)
        
        # Description text
        self.desc_label = ttk.Label(
            desc_frame,
            text="",
            style='Description.TLabel',
            justify='left'
        )
        self.desc_label.pack(anchor='nw', fill='both')
        
        # Update description for default selection
        self.update_description()
        
        # Spacer to push buttons down
        ttk.Frame(main_frame, height=10).pack()
        
        # Button frame - explicitly pack at bottom
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, pady=10)
        
        # Submit button
        self.launch_button = ttk.Button(
            button_frame,
            text="Submit",
            style='Launch.TButton',
            command=self.launch_advisor,
            width=15
        )
        self.launch_button.grid(row=0, column=0, padx=5)
        
        # Exit button
        exit_btn = ttk.Button(
            button_frame,
            text="Exit",
            command=self.root.quit,
            width=15
        )
        exit_btn.grid(row=0, column=1, padx=5)
        
        # Status bar - pack at very bottom
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        
        self.status_var = tk.StringVar(value="Ready to launch")
        status_bar = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=('Helvetica', 9),
            padding=5
        )
        status_bar.pack(fill=tk.X)
    
    def on_mode_change(self, event=None):
        """Handle mode selection change"""
        self.update_description()
    
    def update_description(self):
        """Update description based on selected mode"""
        mode = self.mode_var.get()
        
        descriptions = {
            "Migration Advisor Lite": (
                "🎯 Quick Migration Assessment\n\n"
                "Perfect for rapid evaluations and proof-of-concepts.\n\n"
                "Features:\n"
                "• Streamlined workflow with essential analysis\n"
                "• Faster execution time (5-10 minutes)\n"
                "• Core architecture analysis and recommendations\n"
                "• Basic TCO estimation\n"
                "• Simplified migration roadmap\n"
                "• PDF report generation\n\n"
                "Best for: Initial assessments, quick wins, and straightforward migrations"
            ),
            "Migration Advisor Regular": (
                "🔬 Comprehensive Migration Analysis\n\n"
                "Full-featured migration advisory with deep analysis.\n\n"
                "Features:\n"
                "• Complete multi-agent workflow\n"
                "• Interactive Q&A session for clarifications\n"
                "• Detailed architecture analysis\n"
                "• Comprehensive TCO comparison\n"
                "• Step-by-step migration roadmap\n"
                "• Architecture diagrams generation\n"
                "• Detailed PDF report with all findings\n\n"
                "Best for: Complex migrations, enterprise deployments, and detailed planning"
            )
        }
        
        self.desc_label.config(text=descriptions.get(mode, ""))
    
    def launch_advisor(self):
        """Launch the selected migration advisor in a separate thread"""
        mode = self.mode_var.get()
        
        # Determine which script to run
        if mode == "Migration Advisor Lite":
            script_name = "sagemaker_migration_advisor_lite.py"
            display_name = "Migration Advisor Lite"
        else:
            script_name = "sagemaker_migration_advisor.py"
            display_name = "Migration Advisor Regular"
        
        # Get script path
        script_path = Path(__file__).parent / script_name
        
        if not script_path.exists():
            messagebox.showerror(
                "Error",
                f"Script not found: {script_name}\n\nPlease ensure the file exists in the same directory."
            )
            return
        
        # Disable launch button to prevent multiple launches
        if self.launch_button:
            self.launch_button.config(state='disabled', text='Running...')
        
        # Update status
        self.status_var.set(f"🚀 Launching {display_name}... Please wait, this may take several minutes...")
        self.root.update()
        
        # Run in separate thread to keep GUI responsive
        thread = threading.Thread(
            target=self._run_advisor_thread,
            args=(script_path, display_name),
            daemon=True
        )
        thread.start()
    
    def _run_advisor_thread(self, script_path: Path, display_name: str):
        """Run the advisor in a separate thread"""
        try:
            # Launch the selected advisor with Streamlit
            result = subprocess.run(
                ["streamlit", "run", str(script_path)],
                cwd=script_path.parent,
                check=False,
                capture_output=False  # Let output go to console
            )
            
            # Schedule GUI update in main thread
            self.root.after(0, self._on_advisor_complete, result.returncode, display_name)
        
        except FileNotFoundError:
            # Streamlit not found
            error_msg = (
                "Streamlit is not installed or not in PATH.\n\n"
                "Please install it with:\n"
                "pip install streamlit"
            )
            self.root.after(0, self._on_advisor_error, error_msg, display_name)
        except Exception as e:
            # Schedule error handling in main thread
            self.root.after(0, self._on_advisor_error, str(e), display_name)
    
    def _on_advisor_complete(self, return_code: int, display_name: str):
        """Handle advisor completion (runs in main thread)"""
        # Re-enable submit button
        if self.launch_button:
            self.launch_button.config(state='normal', text='Submit')
        
        if return_code == 0:
            self.status_var.set(f"✅ {display_name} completed successfully")
            messagebox.showinfo(
                "Success",
                f"{display_name} completed successfully!\n\nCheck the output directory for results."
            )
        else:
            self.status_var.set(f"⚠️ {display_name} exited with errors (code: {return_code})")
            messagebox.showwarning(
                "Warning",
                f"{display_name} exited with return code {return_code}\n\nCheck the console for details."
            )
    
    def _on_advisor_error(self, error_msg: str, display_name: str):
        """Handle advisor error (runs in main thread)"""
        # Re-enable submit button
        if self.launch_button:
            self.launch_button.config(state='normal', text='Submit')
        
        self.status_var.set("❌ Error launching advisor")
        messagebox.showerror(
            "Error",
            f"Failed to launch {display_name}:\n\n{error_msg}"
        )
    
    def run(self):
        """Run the GUI application"""
        self.root.mainloop()


def cli_launcher():
    """Command-line interface launcher (fallback when GUI not available)"""
    print("\n" + "="*60)
    print("  SageMaker Migration Advisor Launcher")
    print("="*60 + "\n")
    
    print("Select Migration Mode:\n")
    print("1. Migration Advisor Lite")
    print("   - Quick assessment and recommendations")
    print("   - Faster execution (5-10 minutes)")
    print("   - Essential analysis and basic TCO")
    print()
    print("2. Migration Advisor Regular")
    print("   - Comprehensive analysis with Q&A")
    print("   - Detailed TCO and architecture diagrams")
    print("   - Complete migration roadmap")
    print()
    
    while True:
        choice = input("Enter your choice (1 or 2): ").strip()
        
        if choice == "1":
            script_name = "sagemaker_migration_advisor_lite.py"
            display_name = "Migration Advisor Lite"
            break
        elif choice == "2":
            script_name = "sagemaker_migration_advisor.py"
            display_name = "Migration Advisor Regular"
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")
    
    # Get script path
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        print(f"\n❌ Error: Script not found: {script_name}")
        print(f"   Please ensure the file exists in: {script_path.parent}")
        sys.exit(1)
    
    print(f"\n🚀 Launching {display_name}...\n")
    print("="*60 + "\n")
    
    try:
        # Launch the selected advisor with Streamlit
        result = subprocess.run(
            ["streamlit", "run", str(script_path)],
            cwd=script_path.parent
        )
        
        sys.exit(result.returncode)
    
    except FileNotFoundError:
        print("\n❌ Error: Streamlit is not installed or not in PATH")
        print("\nPlease install Streamlit:")
        print("  pip install streamlit")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error launching {display_name}: {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    # Check if running in GUI mode
    if GUI_AVAILABLE and not any(arg in sys.argv for arg in ['--cli', '--no-gui', '-c']):
        try:
            launcher = MigrationAdvisorLauncher()
            launcher.run()
        except Exception as e:
            print(f"GUI initialization failed: {e}")
            print("Falling back to CLI mode...\n")
            cli_launcher()
    else:
        cli_launcher()


if __name__ == "__main__":
    main()
