"""Setup wizard for first-time configuration."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from .manager import ConfigManager, Config


class SetupWizard:
    """GUI wizard for initial configuration."""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.root = tk.Tk()
        self.root.title("BudgetFlow Setup Wizard")
        self.root.geometry("600x500")
        
        # Variables
        self.gemini_key_var = tk.StringVar()
        self.service_account_var = tk.StringVar()
        self.root_folder_var = tk.StringVar()
        self.polling_var = tk.IntVar(value=5)
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create wizard UI components."""
        # Title
        title = ttk.Label(
            self.root,
            text="BudgetFlow Setup",
            font=("Arial", 16, "bold")
        )
        title.pack(pady=20)
        
        # Main frame
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Gemini API Key
        ttk.Label(frame, text="Gemini API Key:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.gemini_key_var, width=50, show="*").grid(
            row=0, column=1, pady=5, padx=5
        )
        
        # Service Account
        ttk.Label(frame, text="Service Account File:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.service_account_var, width=40).grid(
            row=1, column=1, pady=5, padx=5
        )
        ttk.Button(frame, text="Browse", command=self._browse_service_account).grid(
            row=1, column=2, pady=5
        )
        
        # Root Folder ID
        ttk.Label(frame, text="Root Folder ID:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.root_folder_var, width=50).grid(
            row=2, column=1, pady=5, padx=5
        )
        
        # Polling Interval
        ttk.Label(frame, text="Polling Interval (minutes):").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Spinbox(frame, from_=1, to=60, textvariable=self.polling_var, width=10).grid(
            row=3, column=1, sticky=tk.W, pady=5, padx=5
        )
        
        # Buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Validate & Save", command=self._validate_and_save).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="Cancel", command=self.root.quit).pack(
            side=tk.LEFT, padx=5
        )
        
        # Status label
        self.status_label = ttk.Label(self.root, text="", foreground="blue")
        self.status_label.pack(pady=10)
    
    def _browse_service_account(self):
        """Open file dialog for service account selection."""
        filename = filedialog.askopenfilename(
            title="Select Service Account JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.service_account_var.set(filename)
    
    def _validate_and_save(self):
        """Validate inputs and save configuration."""
        self.status_label.config(text="Validating...", foreground="blue")
        self.root.update()
        
        try:
            # Create config object
            config = Config(
                gemini_api_key=self.gemini_key_var.get(),
                service_account_path=self.service_account_var.get(),
                root_folder_id=self.root_folder_var.get(),
                polling_interval_minutes=self.polling_var.get()
            )
            
            # Validate basic fields
            is_valid, message = self.config_manager.validate_config(config)
            if not is_valid:
                messagebox.showerror("Validation Error", message)
                self.status_label.config(text="Validation failed", foreground="red")
                return
            
            # Validate Google Drive access
            self.status_label.config(text="Validating Drive access...", foreground="blue")
            self.root.update()
            
            credentials = service_account.Credentials.from_service_account_file(
                config.service_account_path,
                scopes=[
                    "https://www.googleapis.com/auth/drive",
                    "https://www.googleapis.com/auth/spreadsheets"
                ]
            )
            
            drive_service = build("drive", "v3", credentials=credentials)
            
            # Test Drive access
            try:
                folder = drive_service.files().get(
                    fileId=config.root_folder_id,
                    fields="id,name"
                ).execute()
                
                # Verify Outputs folder exists or create it
                query = f"'{config.root_folder_id}' in parents and name='Outputs' and mimeType='application/vnd.google-apps.folder'"
                results = drive_service.files().list(q=query, fields="files(id,name)").execute()
                
                if not results.get("files"):
                    # Create Outputs folder
                    outputs_metadata = {
                        "name": "Outputs",
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": [config.root_folder_id]
                    }
                    drive_service.files().create(body=outputs_metadata, fields="id").execute()
                    self.status_label.config(text="Created Outputs folder", foreground="green")
                
            except Exception as e:
                messagebox.showerror(
                    "Drive Access Error",
                    f"Cannot access root folder: {e}\n\nMake sure the folder is shared with the service account."
                )
                self.status_label.config(text="Drive validation failed", foreground="red")
                return
            
            # Save configuration
            self.config_manager.save_config(config)
            
            messagebox.showinfo(
                "Success",
                "Configuration saved successfully!\n\nBudgetFlow is ready to run."
            )
            self.status_label.config(text="Configuration saved!", foreground="green")
            self.root.after(1000, self.root.quit)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {e}")
            self.status_label.config(text="Error occurred", foreground="red")
    
    def run(self):
        """Run the setup wizard."""
        self.root.mainloop()


def run_setup_wizard():
    """Entry point for setup wizard."""
    wizard = SetupWizard()
    wizard.run()


if __name__ == "__main__":
    run_setup_wizard()
