

import json
import os
import sys
import threading
from queue import Queue
import keyring

import ttkbootstrap as ttk
from ttkbootstrap.constants import (SOLID, DISABLED, NORMAL, END, NSEW, W, X,
                                    LEFT, BOTH)
from tkinter import messagebox, scrolledtext

from bot import WoonnetBot

# --- CONSTANTS ---
APP_NAME = "WoonnetBot"
def get_app_dir():
    """Get the application directory in APPDATA."""
    appdata = os.environ.get('APPDATA')
    if not appdata:
        # Fallback to a local directory if APPDATA is not set
        return os.path.join(os.path.expanduser("~"), f".{APP_NAME}")
    return os.path.join(appdata, APP_NAME)

APP_DIR = get_app_dir()
PREFS_FILE = os.path.join(APP_DIR, 'user_prefs.json')
SERVICE_ID = f"python:{APP_NAME}"

# --- GUI APPLICATION ---

class App(ttk.Window):
    def __init__(self):
        super().__init__(
            themename="litera",
            title="Woonnet Rijnmond Bot",
            size=(500, 600),
            resizable=(False, False)
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.bot_thread = None
        self.status_queue = Queue()
        self.bot_instance = None

        # --- Widgets ---
        self.create_widgets()
        self.layout_widgets()

        # --- Preferences & State ---
        self.load_preferences()
        self.update_ui_state()
        self.after(100, self.process_status_queue)

    def create_widgets(self):
        """Creates all the GUI widgets."""
        # --- Main Frame ---
        self.container = ttk.Frame(self, padding=20)

        # --- Credentials ---
        cred_frame = ttk.Labelframe(self.container, text="Credentials", padding=15)
        self.user_label = ttk.Label(cred_frame, text="Username:")
        self.user_entry = ttk.Entry(cred_frame)
        self.pass_label = ttk.Label(cred_frame, text="Password:")
        self.pass_entry = ttk.Entry(cred_frame, show="*")
        self.remember_check = ttk.Checkbutton(
            cred_frame, text="Remember Me", command=self.handle_remember_me
        )

        # --- Mode Selection ---
        mode_frame = ttk.Labelframe(self.container, text="Operation Mode", padding=15)
        self.mode = ttk.StringVar(value="run_now")
        self.run_now_radio = ttk.Radiobutton(
            mode_frame, text="Run Now", variable=self.mode, value="run_now",
            command=self.update_ui_state
        )
        self.run_scheduled_radio = ttk.Radiobutton(
            mode_frame, text="Run in Background (Wait for 6-8 PM)",
            variable=self.mode, value="run_scheduled", command=self.update_ui_state
        )
        self.test_mode_radio = ttk.Radiobutton(
            mode_frame, text="Test Mode", variable=self.mode, value="test_mode",
            command=self.update_ui_state
        )

        # --- Run Now & Scheduled Options ---
        self.run_options_frame = ttk.Frame(mode_frame)
        self.num_label = ttk.Label(self.run_options_frame, text="Apply to:")
        self.num_spinbox = ttk.Spinbox(self.run_options_frame, from_=1, to=20, width=5)
        self.max_check = ttk.Checkbutton(
            self.run_options_frame, text="Max Available", command=self.toggle_spinbox
        )

        # --- Test Mode Options ---
        self.test_options_frame = ttk.Frame(mode_frame)
        self.test_id_label = ttk.Label(self.test_options_frame, text="Listing ID:")
        self.test_id_entry = ttk.Entry(self.test_options_frame, width=15)
        self.apply_in_test_check = ttk.Checkbutton(
            self.test_options_frame, text="Actually Click Apply"
        )

        # --- Controls & Status ---
        control_frame = ttk.Frame(self.container)
        self.start_button = ttk.Button(
            control_frame, text="Start Bot", command=self.start_bot
        )
        self.stop_button = ttk.Button(
            control_frame, text="Stop Bot", command=self.stop_bot, state=DISABLED
        )
        
        status_frame = ttk.Labelframe(self, text="Status Log", padding=(15, 10))
        self.log_area = scrolledtext.ScrolledText(
            status_frame, wrap="word", state=DISABLED, height=10,
            font=("Segoe UI", 9)
        )

        # Pack widgets into their respective frames
        self.user_label.pack(anchor=W)
        self.user_entry.pack(fill=X, pady=(2, 5))
        self.pass_label.pack(anchor=W)
        self.pass_entry.pack(fill=X, pady=(2, 10))
        self.remember_check.pack(anchor=W)
        
        self.run_now_radio.pack(anchor=W)
        self.run_scheduled_radio.pack(anchor=W)
        self.num_label.pack(side=LEFT, padx=(20, 5))
        self.num_spinbox.pack(side=LEFT)
        self.max_check.pack(side=LEFT, padx=5)
        
        self.test_mode_radio.pack(anchor=W, pady=(5, 0))
        self.test_id_label.pack(side=LEFT, padx=(20, 5))
        self.test_id_entry.pack(side=LEFT)
        self.apply_in_test_check.pack(side=LEFT, padx=5)

        self.start_button.pack(side=LEFT, fill=X, expand=True, ipady=5, padx=(0, 5))
        self.stop_button.pack(side=LEFT, fill=X, expand=True, ipady=5, padx=(5, 0))
        
        self.log_area.pack(fill=BOTH, expand=True)

        # Place frames in the main layout
        cred_frame.pack(fill=X, pady=(0, 10))
        mode_frame.pack(fill=X, pady=(0, 15))
        self.run_options_frame.pack(anchor=W, fill=X, pady=5)
        self.test_options_frame.pack(anchor=W, fill=X, pady=5)
        control_frame.pack(fill=X, pady=(0, 15))
        
        self.container.grid(row=0, column=0, sticky=NSEW, padx=10, pady=10)
        status_frame.grid(row=1, column=0, sticky=NSEW, padx=10, pady=(0, 10))

    def layout_widgets(self):
        """Lays out the main widgets in the window."""
        # This is now handled within create_widgets to keep related code together.
        pass

    def update_ui_state(self):
        """Enable/disable parts of the UI based on the selected mode."""
        mode = self.mode.get()
        
        # Run options
        is_run_mode = mode in ("run_now", "run_scheduled")
        for child in self.run_options_frame.winfo_children():
            child.configure(state=NORMAL if is_run_mode else DISABLED) # type: ignore
        if is_run_mode:
            self.toggle_spinbox()
        else:
            self.num_spinbox.config(state=DISABLED)
            self.max_check.config(state=DISABLED)

        # Test options
        is_test_mode = mode == "test_mode"
        for child in self.test_options_frame.winfo_children():
            child.configure(state=NORMAL if is_test_mode else DISABLED) # type: ignore

    def toggle_spinbox(self):
        """Enable/disable the spinbox based on the 'Max' checkbox."""
        if self.max_check.instate(['selected']):
            self.num_spinbox.config(state=DISABLED)
        else:
            self.num_spinbox.config(state=NORMAL)

    def log(self, message):
        """Adds a message to the log area on the main thread."""
        self.log_area.config(state=NORMAL)
        self.log_area.insert(END, f"{message}\n")
        self.log_area.config(state=DISABLED)
        self.log_area.see(END)

    def process_status_queue(self):
        """Processes messages from the bot thread's status queue."""
        while not self.status_queue.empty():
            message = self.status_queue.get_nowait()
            self.log(message)
        self.after(100, self.process_status_queue)

    def load_preferences(self):
        """Loads user preferences from the JSON file and keyring."""
        self.log("Loading preferences...")
        try:
            # Load username from keyring first
            stored_user = keyring.get_password(SERVICE_ID, "username")
            if stored_user:
                self.user_entry.insert(0, stored_user)
                # If we have a user, try to get their password
                stored_pass = keyring.get_password(SERVICE_ID, stored_user)
                if stored_pass:
                    self.pass_entry.insert(0, stored_pass)
                    self.remember_check.invoke() # Check the box only if both are found

            # Load other non-sensitive settings from JSON file
            if os.path.exists(PREFS_FILE):
                with open(PREFS_FILE, 'r') as f:
                    prefs = json.load(f)
                    self.mode.set(prefs.get("mode", "run_now"))
                    self.num_spinbox.set(prefs.get("num_to_apply", 1))
                    if prefs.get("use_max", False): self.max_check.invoke()
                    self.test_id_entry.insert(0, prefs.get("test_id", ""))
                    if prefs.get("apply_in_test", False): self.apply_in_test_check.invoke()
            else:
                # Default values if no prefs file
                self.num_spinbox.set(1)
        except Exception as e:
            self.log(f"Could not load preferences: {e}")

    def save_preferences(self):
        """Saves non-sensitive preferences to a JSON file."""
        prefs = {
            "mode": self.mode.get(),
            "use_max": self.max_check.instate(['selected']),
            "num_to_apply": int(self.num_spinbox.get() or 1),
            "test_id": self.test_id_entry.get(),
            "apply_in_test": self.apply_in_test_check.instate(['selected']),
        }
        try:
            os.makedirs(os.path.dirname(PREFS_FILE), exist_ok=True)
            with open(PREFS_FILE, 'w') as f:
                json.dump(prefs, f, indent=4)
            self.log("Settings saved.")
        except Exception as e:
            self.log(f"Error saving settings: {e}")

    def handle_remember_me(self):
        """Handles storing or deleting credentials from keyring."""
        # This method is now primarily for manual user interaction
        if self.remember_check.instate(['selected']):
            self.log("Credentials will be saved on the next run.")
        else:
            # User is unchecking the box, so we should delete saved credentials
            username = self.user_entry.get() # Get current username to delete its password
            try:
                if keyring.get_password(SERVICE_ID, "username"):
                    keyring.delete_password(SERVICE_ID, "username")
                if username and keyring.get_password(SERVICE_ID, username):
                    keyring.delete_password(SERVICE_ID, username)
                self.log("Saved credentials have been removed.")
            except Exception as e:
                self.log(f"Could not remove credentials: {e}")

    def start_bot(self):
        """Validates inputs and starts the bot in a new thread."""
        self.save_preferences() # Save settings on every run

        username = self.user_entry.get()
        password = self.pass_entry.get()

        if not username or not password:
            messagebox.showerror("Input Error", "Username and Password are required.")
            return

        # Handle credential saving
        if self.remember_check.instate(['selected']):
            try:
                keyring.set_password(SERVICE_ID, "username", username)
                keyring.set_password(SERVICE_ID, username, password)
                self.log("Credentials saved securely.")
            except Exception as e:
                self.log(f"Failed to save credentials: {e}")

        self.start_button.config(state=DISABLED)
        self.stop_button.config(state=NORMAL)
        self.log_area.configure(state=NORMAL)
        self.log_area.delete('1.0', END) # Clear log
        self.log_area.configure(state=DISABLED)

        self.bot_instance = WoonnetBot(self.status_queue)
        
        # Collect args for the bot thread
        mode = self.mode.get()
        args = {
            "username": username,
            "password": password,
        }
        target_method = None

        if mode == "run_now":
            target_method = self.bot_instance.run
            args |= {
                "use_max": self.max_check.instate(['selected']),
                "num_to_apply": int(self.num_spinbox.get() or 1)
            }
        elif mode == "run_scheduled":
            target_method = self.bot_instance.run_scheduled
            args |= {
                "use_max": self.max_check.instate(['selected']),
                "num_to_apply": int(self.num_spinbox.get() or 1)
            }
        elif mode == "test_mode":
            target_method = self.bot_instance.run_test
            test_id = self.test_id_entry.get()
            if not test_id:
                messagebox.showerror("Input Error", "Test ID is required for Test Mode.")
                self.on_bot_finished()
                return
            args |= {
                "listing_id": test_id,
                "actually_apply": self.apply_in_test_check.instate(['selected'])
            }

        # Start the thread
        self.bot_thread = threading.Thread(
            target=self.run_bot_wrapper,
            args=(target_method, args),
            daemon=True
        )
        self.bot_thread.start()

    def run_bot_wrapper(self, target_method, args):
        """A wrapper to run the bot method and handle cleanup."""
        try:
            target_method(**args)
        except Exception as e:
            self.status_queue.put(f"A critical error occurred in the bot thread: {e}")
        finally:
            if self.bot_instance:
                self.bot_instance.quit()
            self.after(0, self.on_bot_finished)

    def stop_bot(self):
        """Stops the bot thread and quits the webdriver."""
        self.log("Stop command received. Shutting down...")
        if self.bot_instance:
            # The quit method will be called in the thread's finally block.
            # Forcing a quit here can be problematic. We just signal the end.
            self.bot_instance.quit() # This will attempt to close the browser.
        self.on_bot_finished()

    def on_bot_finished(self):
        """Resets the UI when the bot has finished its run."""
        self.start_button.config(state=NORMAL)
        self.stop_button.config(state=DISABLED)
        self.bot_thread = None
        self.bot_instance = None
        self.log("Bot has stopped.")

    def on_closing(self):
        """Handles the window closing event."""
        if self.bot_thread and self.bot_thread.is_alive():
            if messagebox.askyesno("Exit", "Bot is still running. Are you sure you want to exit?"):
                self.stop_bot()
                self.destroy()
            else:
                return
        
        self.save_preferences()
        self.destroy()


if __name__ == "__main__":
    # Ensure the AppData directory exists
    if not os.path.exists(os.path.dirname(PREFS_FILE)):
        os.makedirs(os.path.dirname(PREFS_FILE))
        
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
