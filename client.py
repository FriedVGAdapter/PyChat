import socket
import threading
import time
import sys
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import json
import os

class Client:
    FIXED_SERVER_CONTACT_NAME = "Server Messages"
    FIXED_SERVER_CONTACT_IP = "127.0.0.1" 

    def __init__(self) -> None:
        self.host = None
        self.port = None
        self.connected = False
        self.client_socket = None
        self.receiver_thread = None
        self.servers_file = "client_servers.json"
        self.servers = []
        self.current_server_index = -1

        self.contacts_file = "client_contacts.json"
        self.contacts = []
        self.current_contact_index = -1

        self.blocked_ips_file = "blocked_ips.json"
        self.blocked_ips = set()

        self.chat_history_dir = "chat_histories"
        os.makedirs(self.chat_history_dir, exist_ok=True)

        self.gui_message_buffer = []
        self.gui_update_scheduled = False

        self.manage_contacts_window = None
        self.manage_contacts_listbox = None
        self.add_contact_button = None
        self.edit_contact_button = None
        self.delete_contact_button = None
        self.delete_history_button = None
        self.block_unblock_button = None
        self.manage_window_selected_contact_label = None

        self._setup_gui()
        self._load_servers_automatically()
        self._load_contacts_automatically()
        self._load_blocked_ips()

        if self.servers:
            self.current_server_index = 0
            self.server_names.set(self.servers[self.current_server_index]['name'])
            self._connect()
        else:
            self._update_status("No servers configured. Please add a server to connect.")

        self._load_chat_history_for_selected_contact()
        self._update_title_bar()

        self.root.mainloop()

    def _setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Chat Client")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.configure(bg="gray15")
        self.root.geometry("1000x750")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.main_frame = tk.Frame(self.root, bg="gray15")
        self.main_frame.grid(row=0, column=0, sticky="nsew")

        self.main_frame.grid_rowconfigure(0, weight=0)
        self.main_frame.grid_rowconfigure(1, weight=0)
        self.main_frame.grid_rowconfigure(2, weight=1)
        self.main_frame.grid_rowconfigure(3, weight=0)
        self.main_frame.grid_rowconfigure(4, weight=0)
        self.main_frame.grid_columnconfigure(0, weight=1)

        toolbar_frame = tk.Frame(self.main_frame, bd=2, relief=tk.RAISED, bg="gray30")
        toolbar_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        toolbar_frame.grid_columnconfigure(0, weight=1)

        self.chat_title_label = tk.Label(self.main_frame, text="Select a contact to start chatting", 
                                       bg="gray20", fg="white", font=("Consolas", 12, "bold"), anchor=tk.W)
        self.chat_title_label.grid(row=1, column=0, sticky="ew", padx=5, pady=0)

        self.text_area = scrolledtext.ScrolledText(
            self.main_frame,
            wrap=tk.WORD,
            bg="black", fg="white", insertbackground="white",
            font=("Consolas", 12), bd=0, relief="flat"
        )
        self.text_area.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.text_area.config(state=tk.DISABLED)

        self.text_area.tag_configure('white', foreground='white')

        input_frame = tk.Frame(self.main_frame, bg="gray25")
        input_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        input_frame.grid_columnconfigure(0, weight=1)

        self.message_entry = tk.Entry(
            input_frame,
            font=("Consolas", 12), bg="gray20", fg="white", insertbackground="white",
            bd=0, relief="flat"
        )
        self.message_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.message_entry.bind("<Return>", self._send_message_from_entry)
        
        self.send_button = tk.Button(
            input_frame,
            text="Send",
            command=self._send_message_from_entry,
            bg="gray30", fg="white", font=("Consolas", 12),
            activebackground="gray40", activeforeground="white"
        )
        self.send_button.grid(row=0, column=1, sticky="e", padx=5, pady=5)

        self.status_bar = tk.Label(self.main_frame, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W, 
                                    bg="gray20", fg="white", font=("Consolas", 9))
        self.status_bar.grid(row=4, column=0, sticky="ew")

        self._setup_menu()
        self._update_status("GUI Initialized. Load or add a server.")

    def _setup_menu(self):
        menubar = tk.Menu(self.root, bg="gray25", fg="white")
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0, bg="gray25", fg="white")
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Clear Chat History (Current Contact)", command=self._delete_chat_history)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)

        self.server_management_menu = tk.Menu(menubar, tearoff=0, bg="gray25", fg="white")
        menubar.add_cascade(label="Servers", menu=self.server_management_menu)
        self.server_management_menu.add_command(label="Add Server...", command=self._show_add_server_dialog)
        self.server_management_menu.add_command(label="Edit Server...", command=self._show_update_server_dialog)
        self.server_management_menu.add_command(label="Delete Server", command=self._remove_server)
        self.server_management_menu.add_separator()
        self.server_management_menu.add_command(label="Disconnect", command=self._disconnect)
        self.server_management_menu.add_separator()
        
        self.server_names = tk.StringVar(self.root)
        self.server_names.set("No servers loaded")
        self.server_names.trace("w", self._on_server_selected)
        
        self.select_server_submenu = tk.Menu(self.server_management_menu, tearoff=0, bg="gray25", fg="white")
        self.server_management_menu.add_cascade(label="Select Server", menu=self.select_server_submenu)

        self.contacts_menu = tk.Menu(menubar, tearoff=0, bg="gray25", fg="white")
        menubar.add_cascade(label="Contacts", menu=self.contacts_menu)
        self.contacts_menu.add_command(label="Manage Contacts...", command=self._open_manage_contacts_window)
        self.contacts_menu.add_separator()
        self.contacts_menu.add_command(label="No contacts loaded", state=tk.DISABLED)

    def _update_title_bar(self):
        server_name_display = "Not Connected"
        if self.connected and self.current_server_index != -1 and self.current_server_index < len(self.servers):
            server_name_display = self.servers[self.current_server_index]['name']
        
        contact_name_display = "No Contact Selected"
        if self.current_contact_index != -1 and self.current_contact_index < len(self.contacts):
            contact_name_display = self.contacts[self.current_contact_index]['name']
            if contact_name_display.startswith("🚫 "):
                contact_name_display = contact_name_display[2:]
            elif contact_name_display.startswith("❓ "):
                contact_name_display = contact_name_display[2:]

        self.root.title(f"Chat Client - Server: {server_name_display} | Chatting with: {contact_name_display}")

    def _update_status(self, message, color="white"):
        self.status_bar.config(text=message, fg=color)

    def _update_connect_button_state(self):
        pass

    def _update_server_dropdown(self):
        self.select_server_submenu.delete(0, "end")
        if not self.servers:
            self.server_names.set("No servers loaded")
            self.current_server_index = -1
            self.select_server_submenu.add_command(label="No servers loaded", state=tk.DISABLED)
            return

        for i, server in enumerate(self.servers):
            self.select_server_submenu.add_command(label=server['name'], command=lambda value=server['name'], index=i: self._select_server_by_name(value, index))
        
        if self.current_server_index == -1 or self.current_server_index >= len(self.servers):
            self.current_server_index = 0
        self.server_names.set(self.servers[self.current_server_index]['name'])

    def _on_server_selected(self, *args):
        selected_name = self.server_names.get()
        for i, server in enumerate(self.servers):
            if server['name'] == selected_name:
                self.current_server_index = i
                break
        self._disconnect()
        self._connect()
        self._update_title_bar()

    def _select_server_by_name(self, name, index):
        self.server_names.set(name)
        self.current_server_index = index

    def _show_add_server_dialog(self):
        dialog = ServerConfigDialog(self.root, "Add New Server", mode="add")
        if dialog.result:
            name, host, port = dialog.result
            if any(s['name'] == name for s in self.servers):
                messagebox.showwarning("Duplicate Name", f"A server with name '{name}' already exists.")
                return

            new_server = {'name': name, 'host': host, 'port': port}
            self.servers.append(new_server)
            self._update_server_dropdown()
            self.current_server_index = len(self.servers) - 1
            self.server_names.set(name)
            self._update_status(f"Server '{name}' added. (Automatically saved)")
            self._save_servers_automatically()

    def _show_update_server_dialog(self):
        if self.current_server_index == -1 or not self.servers:
            messagebox.showinfo("No Server Selected", "Please select a server to update first.")
            return
        
        current_server = self.servers[self.current_server_index]
        dialog = ServerConfigDialog(self.root, "Edit Server", mode="update", 
                                    initial_name=current_server['name'], 
                                    initial_host=current_server['host'], 
                                    initial_port=current_server['port'])
        
        if dialog.result:
            name, host, port = dialog.result
            for i, s in enumerate(self.servers):
                if s['name'] == name and i != self.current_server_index:
                    messagebox.showwarning("Duplicate Name", f"A server with name '{name}' already exists.")
                    return

            self.servers[self.current_server_index] = {'name': name, 'host': host, 'port': port}
            self._update_server_dropdown()
            self.server_names.set(name)
            self._update_status(f"Server '{name}' updated. (Automatically saved)")
            self._save_servers_automatically()

    def _remove_server(self):
        if self.current_server_index == -1 or not self.servers:
            messagebox.showinfo("No Server Selected", "No server selected to remove.")
            return
        
        removed_name = self.servers[self.current_server_index]['name']
        if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove server '{removed_name}'?"):
            del self.servers[self.current_server_index]
            self.current_server_index = -1
            self._update_server_dropdown()
            self._update_status(f"Server '{removed_name}' removed. (Automatically saved)")
            self._save_servers_automatically()
            if not self.servers:
                self.server_names.set("No servers loaded")

    def _load_servers_automatically(self):
        if os.path.exists(self.servers_file):
            try:
                with open(self.servers_file, "r") as f:
                    self.servers = json.load(f)
                self._update_server_dropdown()
                self._update_status(f"Servers loaded from {self.servers_file}.")
            except json.JSONDecodeError:
                messagebox.showerror("File Error", f"Error reading {self.servers_file}. File might be corrupted.")
                self._update_status(f"Error loading {self.servers_file}.")
            except Exception as e:
                messagebox.showerror("Error", f"An unexpected error occurred while loading servers: {e}")
                self._update_status(f"Error loading servers: {e}")
        else:
            self._update_status(f"No {self.servers_file} found. Start by adding a server.")

    def _save_servers_automatically(self):
        try:
            with open(self.servers_file, "w") as f:
                json.dump(self.servers, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving servers: {e}")
            self._update_status(f"Error saving servers: {e}", "red")

    def _load_contacts_automatically(self):
        if os.path.exists(self.contacts_file):
            try:
                with open(self.contacts_file, "r") as f:
                    self.contacts = json.load(f)
            except json.JSONDecodeError:
                messagebox.showerror("File Error", f"Error reading {self.contacts_file}. File might be corrupted.")
                self._update_status(f"Error loading {self.contacts_file}.")
                self.contacts = []
            except Exception as e:
                messagebox.showerror("Error", f"An unexpected error occurred while loading contacts: {e}")
                self._update_status(f"Error loading contacts: {e}")
                self.contacts = []
        else:
            self._update_status(f"No {self.contacts_file} found. Add contacts to chat with others.")
        
        server_contact_exists = False
        for i, contact in enumerate(self.contacts):
            if contact.get('ip') == self.FIXED_SERVER_CONTACT_IP:
                if contact.get('name') != self.FIXED_SERVER_CONTACT_NAME:
                    self.contacts[i]['name'] = self.FIXED_SERVER_CONTACT_NAME
                server_contact_exists = True
                if i != 0:
                    fixed_contact = self.contacts.pop(i)
                    self.contacts.insert(0, fixed_contact)
                break
        
        if not server_contact_exists:
            self.contacts.insert(0, {'name': self.FIXED_SERVER_CONTACT_NAME, 'ip': self.FIXED_SERVER_CONTACT_IP})
            self._save_contacts_automatically()

        self._populate_contacts_listbox()
        self._update_status(f"Contacts loaded. Fixed contact '{self.FIXED_SERVER_CONTACT_NAME}' ensured.")

    def _save_contacts_automatically(self):
        try:
            with open(self.contacts_file, "w") as f:
                json.dump(self.contacts, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving contacts: {e}")
            self._update_status(f"Error saving contacts: {e}", "red")

    def _populate_contacts_listbox(self):
        self.contacts_menu.delete(2, tk.END) 

        if not self.contacts:
            self.contacts_menu.add_command(label="No contacts loaded", state=tk.DISABLED)
            self.current_contact_index = -1
            self.chat_title_label.config(text="Select a contact to start chatting")
            return

        for i, contact in enumerate(self.contacts):
            display_name = contact['name']
            if contact['ip'] in self.blocked_ips:
                display_name = "🚫 " + display_name
            elif contact['name'].startswith("Unknown User"):
                display_name = "❓ " + display_name
            
            self.contacts_menu.add_command(label=display_name, command=lambda idx=i: self._select_contact_from_menu(idx))
        
        if self.manage_contacts_window and self.manage_contacts_window.winfo_exists():
            self.manage_contacts_listbox.delete(0, tk.END)
            for i, contact in enumerate(self.contacts):
                display_name = contact['name']
                fg_color = 'white'

                if contact['ip'] in self.blocked_ips:
                    display_name = "🚫 " + display_name
                    fg_color = 'red'
                elif contact['name'].startswith("Unknown User"):
                    display_name = "❓ " + display_name
                    fg_color = 'orange'
                
                self.manage_contacts_listbox.insert(tk.END, display_name)
                self.manage_contacts_listbox.itemconfig(tk.END, fg=fg_color)
            
            if self.current_contact_index != -1 and self.current_contact_index < len(self.contacts):
                self.manage_contacts_listbox.selection_set(self.current_contact_index)
                self.manage_contacts_listbox.activate(self.current_contact_index)

        if self.current_contact_index == -1 or self.current_contact_index >= len(self.contacts):
            self.current_contact_index = 0
        
        self._update_selected_contact_label()
        self._update_contact_button_states()
        self._load_chat_history_for_selected_contact()

    def _select_contact_from_menu(self, index):
        self.current_contact_index = index
        self._update_selected_contact_label()
        self._load_chat_history_for_selected_contact()
        self._update_title_bar()
        self.chat_title_label.config(text=self._get_current_contact_display_name())
        if self.manage_contacts_window and self.manage_contacts_window.winfo_exists():
            self.manage_contacts_listbox.selection_clear(0, tk.END)
            self.manage_contacts_listbox.selection_set(self.current_contact_index)
            self.manage_contacts_listbox.activate(self.current_contact_index)

    def _on_contact_selected(self, event):
        selected_indices = self.manage_contacts_listbox.curselection()
        if selected_indices:
            self.current_contact_index = selected_indices[0]
            self._update_selected_contact_label_in_manage_window() 
            self._load_chat_history_for_selected_contact()
        else:
            self.current_contact_index = -1
            self.manage_window_selected_contact_label.config(text="Selected: None")
            self.text_area.config(state=tk.NORMAL)
            self.text_area.delete(1.0, tk.END)
            self.text_area.config(state=tk.DISABLED)
        self._update_contact_button_states()
        self._update_title_bar()
        self.chat_title_label.config(text=self._get_current_contact_display_name())

    def _get_current_contact_display_name(self):
        if self.current_contact_index != -1 and self.current_contact_index < len(self.contacts):
            selected_contact = self.contacts[self.current_contact_index]
            display_name = selected_contact['name']
            if display_name.startswith("🚫 "):
                display_name = display_name[2:]
            elif display_name.startswith("❓ "):
                display_name = display_name[2:]
            return f"Chat with: {display_name} ({selected_contact['ip']})"
        return "Select a contact to start chatting"

    def _update_selected_contact_label(self):
        pass

    def _update_selected_contact_label_in_manage_window(self):
        if self.manage_contacts_window and self.manage_contacts_window.winfo_exists():
            if self.current_contact_index != -1 and self.current_contact_index < len(self.contacts):
                selected_contact = self.contacts[self.current_contact_index]
                display_name = selected_contact['name']
                if display_name.startswith("🚫 "):
                    display_name = display_name[2:]
                elif display_name.startswith("❓ "):
                    display_name = display_name[2:]
                self.manage_window_selected_contact_label.config(text=f"Selected: {display_name} ({selected_contact['ip']})")
            else:
                self.manage_window_selected_contact_label.config(text="Selected: None")

    def _update_contact_button_states(self):
        if not (self.manage_contacts_window and self.manage_contacts_window.winfo_exists()):
            return

        if self.current_contact_index == -1:
            self.add_contact_button.config(state=tk.NORMAL)
            self.edit_contact_button.config(state=tk.DISABLED)
            self.delete_contact_button.config(state=tk.DISABLED)
            self.delete_history_button.config(state=tk.DISABLED)
            self.block_unblock_button.config(state=tk.DISABLED, text="🚫 Block")
            return

        selected_contact = self.contacts[self.current_contact_index]
        is_fixed_server_contact = (selected_contact['ip'] == self.FIXED_SERVER_CONTACT_IP)
        is_blocked = (selected_contact['ip'] in self.blocked_ips)

        self.add_contact_button.config(state=tk.NORMAL)
        self.edit_contact_button.config(state=tk.DISABLED if is_fixed_server_contact else tk.NORMAL)
        self.delete_contact_button.config(state=tk.DISABLED if is_fixed_server_contact else tk.NORMAL)
        self.delete_history_button.config(state=tk.NORMAL)
        self.block_unblock_button.config(state=tk.NORMAL, text="✅ Unblock" if is_blocked else "🚫 Block")

    def _open_manage_contacts_window(self):
        if self.manage_contacts_window and self.manage_contacts_window.winfo_exists():
            self.manage_contacts_window.lift()
            return

        self.manage_contacts_window = tk.Toplevel(self.root)
        self.manage_contacts_window.title("Manage Contacts")
        self.manage_contacts_window.configure(bg="gray15")
        self.manage_contacts_window.geometry("500x400")
        self.manage_contacts_window.transient(self.root)
        self.manage_contacts_window.grab_set()
        self.manage_contacts_window.protocol("WM_DELETE_WINDOW", self.manage_contacts_window.destroy)

        manage_frame = tk.Frame(self.manage_contacts_window, bg="gray15")
        manage_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        manage_frame.grid_rowconfigure(0, weight=1)
        manage_frame.grid_columnconfigure(0, weight=1)

        self.manage_window_selected_contact_label = tk.Label(manage_frame, text="Selected: None", 
                                               bg="gray20", fg="cyan", font=("Consolas", 10, "bold"))
        self.manage_window_selected_contact_label.grid(row=0, column=0, sticky="ew", padx=5, pady=2)

        self.manage_contacts_listbox = tk.Listbox(
            manage_frame,
            bg="gray25", fg="white", selectbackground="blue", selectforeground="white",
            font=("Consolas", 10), bd=0, relief="flat"
        )
        self.manage_contacts_listbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.manage_contacts_listbox.bind("<<ListboxSelect>>", self._on_contact_selected)

        contacts_buttons_frame = tk.Frame(manage_frame, bg="gray20")
        contacts_buttons_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        contacts_buttons_frame.grid_columnconfigure(0, weight=1)
        contacts_buttons_frame.grid_columnconfigure(1, weight=1)
        contacts_buttons_frame.grid_columnconfigure(2, weight=1)
        contacts_buttons_frame.grid_columnconfigure(3, weight=1)
        contacts_buttons_frame.grid_columnconfigure(4, weight=1)

        self.add_contact_button = tk.Button(contacts_buttons_frame, text="➕ Add", command=self._show_add_contact_dialog,
                  bg="gray30", fg="white", font=("Consolas", 9, "bold"),
                  activebackground="gray40", activeforeground="white", borderwidth=0, relief="flat"
                 )
        self.add_contact_button.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        self.edit_contact_button = tk.Button(contacts_buttons_frame, text="✏️ Edit", command=self._show_update_contact_dialog,
                  bg="gray30", fg="white", font=("Consolas", 9, "bold"),
                  activebackground="gray40", activeforeground="white", borderwidth=0, relief="flat"
                 )
        self.edit_contact_button.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self.delete_contact_button = tk.Button(contacts_buttons_frame, text="➖ Del", command=self._remove_contact,
                  bg="gray30", fg="white", font=("Consolas", 9, "bold"),
                  activebackground="gray40", activeforeground="white", borderwidth=0, relief="flat"
                 )
        self.delete_contact_button.grid(row=0, column=2, sticky="ew", padx=2, pady=2)
        self.delete_history_button = tk.Button(contacts_buttons_frame, text="🗑️ Hist", command=self._delete_chat_history,
                  bg="gray30", fg="white", font=("Consolas", 9, "bold"),
                  activebackground="gray40", activeforeground="white", borderwidth=0, relief="flat"
                 )
        self.delete_history_button.grid(row=0, column=3, sticky="ew", padx=2, pady=2)
        self.block_unblock_button = tk.Button(contacts_buttons_frame, text="🚫 Block", command=self._toggle_block_contact,
                  bg="gray30", fg="white", font=("Consolas", 9, "bold"),
                  activebackground="gray40", activeforeground="white", borderwidth=0, relief="flat"
                 )
        self.block_unblock_button.grid(row=0, column=4, sticky="ew", padx=2, pady=2)

        self._populate_contacts_listbox()
        self._update_contact_button_states()

        self.root.wait_window(self.manage_contacts_window)

    def _show_add_contact_dialog(self):
        dialog = ContactConfigDialog(self.root, "Add New Contact", mode="add", client_instance=self)
        if dialog.result:
            name, ip = dialog.result
            new_contact = {'name': name, 'ip': ip}
            self.contacts.append(new_contact)
            self._save_contacts_automatically()
            self._populate_contacts_listbox()
            self.current_contact_index = len(self.contacts) - 1
            self._select_contact_from_menu(self.current_contact_index)
            self._update_status(f"Contact '{name}' added. (Automatically saved)")
            self._update_contact_button_states()

    def _show_update_contact_dialog(self):
        if self.current_contact_index == -1 or not self.contacts:
            messagebox.showinfo("No Contact Selected", "Please select a contact to edit first.")
            return
        
        current_contact = self.contacts[self.current_contact_index]
        if current_contact['ip'] == self.FIXED_SERVER_CONTACT_IP:
            messagebox.showwarning("Cannot Edit", "The 'Server Messages' contact cannot be edited.")
            return

        dialog = ContactConfigDialog(self.root, "Edit Contact", mode="update", 
                                    initial_name=current_contact['name'], 
                                    initial_ip=current_contact['ip'],
                                    client_instance=self)
        
        if dialog.result:
            name, ip = dialog.result
            old_ip = self.contacts[self.current_contact_index]['ip']
            self.contacts[self.current_contact_index] = {'name': name, 'ip': ip}
            
            if old_ip != ip:
                old_path = self._get_chat_history_file_path(old_ip)
                new_path = self._get_chat_history_file_path(ip)
                if os.path.exists(old_path):
                    try:
                        os.rename(old_path, new_path)
                        self._update_status(f"Renamed chat history from {old_ip} to {ip}.", "blue")
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to rename chat history file: {e}")
                        self._update_status(f"Error renaming history file: {e}", "red")

            self._save_contacts_automatically()
            self._populate_contacts_listbox()
            self._select_contact_from_menu(self.current_contact_index)
            self._update_status(f"Contact '{name}' updated. (Automatically saved)")
            self._update_contact_button_states()

    def _remove_contact(self):
        if self.current_contact_index == -1 or not self.contacts:
            messagebox.showinfo("No Contact Selected", "No contact selected to remove.")
            return
        
        if self.contacts[self.current_contact_index]['ip'] == self.FIXED_SERVER_CONTACT_IP:
            messagebox.showwarning("Cannot Delete", "The 'Server Messages' contact cannot be deleted.")
            return

        removed_name = self.contacts[self.current_contact_index]['name']
        removed_ip = self.contacts[self.current_contact_index]['ip']
        if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove contact '{removed_name}'?"):
            del self.contacts[self.current_contact_index]
            self.current_contact_index = -1
            self._save_contacts_automatically()
            self._populate_contacts_listbox()
            self._update_status(f"Contact '{removed_name}' removed. (Automatically saved)")
            self._update_selected_contact_label()
            self._delete_chat_history_file(removed_ip)
            self._update_contact_button_states()

    def _load_blocked_ips(self):
        if os.path.exists(self.blocked_ips_file):
            try:
                with open(self.blocked_ips_file, "r") as f:
                    self.blocked_ips = set(json.load(f))
                self._update_status(f"Blocked IPs loaded from {self.blocked_ips_file}.")
            except json.JSONDecodeError:
                messagebox.showerror("File Error", f"Error reading {self.blocked_ips_file}. File might be corrupted.")
                self.blocked_ips = set()
            except Exception as e:
                messagebox.showerror("Error", f"An unexpected error occurred while loading blocked IPs: {e}")
                self.blocked_ips = set()
        else:
            self._update_status(f"No {self.blocked_ips_file} found.")

    def _save_blocked_ips(self):
        try:
            with open(self.blocked_ips_file, "w") as f:
                json.dump(list(self.blocked_ips), f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving blocked IPs: {e}")
            self._update_status(f"Error saving blocked IPs: {e}", "red")

    def _toggle_block_contact(self):
        if self.current_contact_index == -1 or not self.contacts:
            messagebox.showinfo("No Contact Selected", "Please select a contact to block/unblock.")
            return

        selected_contact = self.contacts[self.current_contact_index]
        contact_ip = selected_contact['ip']
        contact_name = selected_contact['name']

        if contact_ip == self.FIXED_SERVER_CONTACT_IP:
            messagebox.showwarning("Cannot Block", "The 'Server Messages' contact cannot be blocked.")
            return

        if contact_ip in self.blocked_ips:
            self.blocked_ips.remove(contact_ip)
            self._update_status(f"Unblocked contact: {contact_name} ({contact_ip})", "green")
        else:
            self.blocked_ips.add(contact_ip)
            self._update_status(f"Blocked contact: {contact_name} ({contact_ip})", "red")
        
        self._save_blocked_ips()
        self._populate_contacts_listbox()
        self._update_contact_button_states()

    def _get_chat_history_file_path(self, contact_ip):
        safe_ip = contact_ip.replace('.', '_').replace(':', '-')
        return os.path.join(self.chat_history_dir, f"chat_history_{safe_ip}.json")

    def _save_message_to_contact_history(self, contact_ip, message):
        if not contact_ip:
            return

        file_path = self._get_chat_history_file_path(contact_ip)
        history = []
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except json.JSONDecodeError:
                self._update_status(f"Corrupted chat history for {contact_ip}. Starting new.", "orange")
                history = []
            except Exception as e:
                self._update_status(f"Error loading chat history for {contact_ip}: {e}", "red")
                history = []

        history.append(message)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving chat history for {contact_ip}: {e}")
            self._update_status(f"Error saving chat history for {contact_ip}: {e}", "red")

    def _load_chat_history_for_selected_contact(self):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)
        self.text_area.config(state=tk.DISABLED)

        if self.current_contact_index == -1 or not self.contacts:
            self._add_message_to_gui("No contact selected. Start a conversation by selecting one.", tag='white')
            self.chat_title_label.config(text="Select a contact to start chatting")
            return

        selected_contact = self.contacts[self.current_contact_index]
        contact_ip = selected_contact['ip']
        file_path = self._get_chat_history_file_path(contact_ip)

        self.chat_title_label.config(text=self._get_current_contact_display_name())

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                for msg in history:
                    self._add_message_to_gui(msg, tag='white') 
                self._update_status(f"Loaded chat history for {selected_contact['name']}.")
            except json.JSONDecodeError:
                self._add_message_to_gui(f"Corrupted chat history for {selected_contact['name']}. Starting fresh.", tag='white')
                self._update_status(f"Corrupted chat history for {selected_contact['name']}.", "orange")
            except Exception as e:
                self._add_message_to_gui(f"Error loading chat history for {selected_contact['name']}: {e}", tag='white')
                self._update_status(f"Error loading chat history for {selected_contact['name']}: {e}", "red")
        else:
            self._add_message_to_gui(f"No chat history found for {selected_contact['name']}. Start typing!", tag='white')
            self._update_status(f"No chat history for {selected_contact['name']}.", "blue")

    def _delete_chat_history(self):
        if self.current_contact_index == -1 or not self.contacts:
            messagebox.showinfo("No Contact Selected", "Please select a contact whose history you want to delete.")
            return

        selected_contact = self.contacts[self.current_contact_index]
        contact_name = selected_contact['name']
        contact_ip = selected_contact['ip']
        
        if messagebox.askyesno("Confirm Delete History", 
                               f"Are you sure you want to delete all chat history for '{contact_name}'? This cannot be undone."):
            self._delete_chat_history_file(contact_ip)
            self._update_status(f"Chat history for '{contact_name}' deleted.", "green")
            self.text_area.config(state=tk.NORMAL)
            self.text_area.delete(1.0, tk.END)
            self.text_area.config(state=tk.DISABLED)
            self._add_message_to_gui(f"Chat history for '{contact_name}' deleted.", tag='white')

    def _delete_chat_history_file(self, contact_ip):
        file_path = self._get_chat_history_file_path(contact_ip)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete chat history file: {e}")
                self._update_status(f"Error deleting history file for {contact_ip}: {e}", "red")

    def _toggle_connection(self):
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        if self.connected:
            self._update_status("Already connected.")
            return 

        if self.current_server_index == -1 or not self.servers:
            self._update_status("No server selected. Please select or add a server to connect to.", "orange")
            return
        
        selected_server = self.servers[self.current_server_index]
        self.host = selected_server['host']
        self.port = selected_server['port']

        self._update_status(f"Connecting to {self.host}:{self.port}...", "yellow")

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            self.connected = True
            self._update_status(f"Connected to {self.host}:{self.port}", "green")

            self.receiver_thread = threading.Thread(target=self.receiver)
            self.receiver_thread.daemon = True
            self.receiver_thread.start()

        except socket.error as e:
            self._add_message_to_gui(f"Connection error: {e}", tag='white')
            self._update_status(f"Connection failed: {e}", "red")
            self.connected = False
            self.client_socket = None 
        except Exception as e:
            self._add_message_to_gui(f"Unexpected error during connection: {e}", tag='white')
            self._update_status(f"Error: {e}", "red")
            self.connected = False
            self.client_socket = None

    def _disconnect(self):
        if not self.connected:
            self._update_status("Not connected.")
            return 

        self._update_status("Disconnecting...", "yellow")
        self.connected = False

        if self.client_socket:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
            except OSError as e:
                self._add_message_to_gui(f"Error closing socket: {e}", tag='white')
            finally:
                self.client_socket = None

        if self.receiver_thread and self.receiver_thread.is_alive():
            self.receiver_thread.join(timeout=1)
            if self.receiver_thread.is_alive():
                self._add_message_to_gui("Receiver thread unresponsive to termination.", tag='white')
        
        self._update_status("Disconnected.", "red")

    def _send_message_from_entry(self, event=None):
        message = self.message_entry.get()
        if not message:
            return

        self.message_entry.delete(0, tk.END)

        if message.lower() == 'quit':
            self._update_status("Client quitting...")
            self._on_closing()
            return

        if not self.connected or not self.client_socket:
            self._update_status("Not connected to server. Connect first.", "orange")
            return

        if self.current_contact_index == -1 or self.current_contact_index >= len(self.contacts):
            self._update_status("No contact selected to send message to.", "orange")
            return

        selected_contact = self.contacts[self.current_contact_index]
        recipient_ip = selected_contact['ip']
        recipient_name = selected_contact['name']

        if recipient_ip in self.blocked_ips:
            self._add_message_to_gui(f"ERROR: Cannot send message to blocked contact {recipient_name} ({recipient_ip}).", tag='white')
            self._update_status(f"Cannot send to blocked contact.", "red")
            return

        try:
            message_data = {}
            if recipient_ip == self.FIXED_SERVER_CONTACT_IP:
                message_data = {
                    "type": "BROADCAST",
                    "recipient": "ALL",
                    "message": message
                }
                display_message = f"YOU (BROADCAST): {message}"
                self._add_message_to_gui(display_message, tag='white')
            else:
                message_data = {
                    "type": "DM",
                    "recipient": recipient_ip,
                    "message": message
                }
                display_message = f"YOU ({recipient_name}): {message}"
                self._add_message_to_gui(display_message, tag='white')
            
            self._save_message_to_contact_history(recipient_ip, display_message)

            json_message = json.dumps(message_data)
            self.client_socket.sendall(json_message.encode('utf-8'))

        except socket.error as e:
            self._add_message_to_gui(f"Error sending message: {e}", tag='white') 
            self._disconnect() 
        except Exception as e:
            self._add_message_to_gui(f"Unexpected error during send: {e}", tag='white')
            self._disconnect()

    def receiver(self):
        while self.connected:
            try:
                data = self.client_socket.recv(1024)
                if not data:
                    self._add_message_to_gui("SERVER: Disconnected.", tag='white')
                    break
                
                received_raw_message = data.decode('utf-8')
                
                try:
                    parsed_message = json.loads(received_raw_message)
                    
                    msg_type = parsed_message.get("type", "UNKNOWN")
                    sender_ip = parsed_message.get("sender_ip", "UNKNOWN")
                    message_content = parsed_message.get("message", "No message content")

                    if sender_ip in self.blocked_ips:
                        print(f"Ignored message from blocked IP: {sender_ip}")
                        continue

                    display_target_ip = self.FIXED_SERVER_CONTACT_IP
                    display_message = ""
                    message_tag = 'white'
                    
                    if msg_type == "DM":
                        sender_contact_name = "UNKNOWN"
                        found_contact = False
                        for contact in self.contacts:
                            if contact['ip'] == sender_ip:
                                sender_contact_name = contact['name']
                                found_contact = True
                                break
                        
                        if not found_contact and sender_ip != self.get_my_ip():
                            new_contact_name = f"Unknown User [{sender_ip}]"
                            new_contact = {'name': new_contact_name, 'ip': sender_ip}
                            self.contacts.append(new_contact)
                            self._save_contacts_automatically()
                            self.root.after(0, self._populate_contacts_listbox)
                            sender_contact_name = new_contact_name

                        display_target_ip = sender_ip
                        display_message = f"DM FROM {sender_contact_name} ({sender_ip}): {message_content}"

                    elif msg_type == "BROADCAST":
                        sender_contact_name = "UNKNOWN"
                        found_contact = False
                        for contact in self.contacts:
                            if contact['ip'] == sender_ip:
                                sender_contact_name = contact['name']
                                found_contact = True
                                break
                        
                        if not found_contact and sender_ip != self.get_my_ip():
                            new_contact_name = f"Unknown User [{sender_ip}]"
                            new_contact = {'name': new_contact_name, 'ip': sender_ip}
                            self.contacts.append(new_contact)
                            self._save_contacts_automatically()
                            self.root.after(0, self._populate_contacts_listbox)
                            sender_contact_name = new_contact_name

                        display_target_ip = self.FIXED_SERVER_CONTACT_IP
                        display_message = f"BROADCAST FROM {sender_contact_name} ({sender_ip}): {message_content}"

                    elif msg_type == "SERVER_DM" or msg_type == "SERVER_BROADCAST":
                        display_target_ip = self.FIXED_SERVER_CONTACT_IP
                        display_message = f"SERVER: {message_content}"

                    elif msg_type == "ERROR":
                        display_target_ip = self.FIXED_SERVER_CONTACT_IP
                        display_message = f"SERVER ERROR: {message_content}"
                    else:
                        display_target_ip = self.FIXED_SERVER_CONTACT_IP
                        display_message = f"UNKNOWN MESSAGE TYPE: {received_raw_message}"

                    self._save_message_to_contact_history(display_target_ip, display_message)

                    current_selected_contact_ip = None
                    if self.current_contact_index != -1 and self.current_contact_index < len(self.contacts):
                        current_selected_contact_ip = self.contacts[self.current_contact_index]['ip']

                    if current_selected_contact_ip == display_target_ip:
                        self._add_message_to_gui(display_message, tag=message_tag)

                except json.JSONDecodeError:
                    display_message = f"RAW SERVER MESSAGE: {received_raw_message}"
                    self._add_message_to_gui(display_message, tag='white')
                    self._save_message_to_contact_history(self.FIXED_SERVER_CONTACT_IP, display_message)
                except Exception as e:
                    error_message = f"ERROR PROCESSING RECEIVED DATA: {e} | RAW: {received_raw_message}"
                    self._add_message_to_gui(error_message, tag='white')
                    self._save_message_to_contact_history(self.FIXED_SERVER_CONTACT_IP, error_message)

            except socket.error as e:
                if self.connected: 
                    self._add_message_to_gui(f"RECEIVER ERROR: {e}", tag='white')
                break 
            except Exception as e:
                self._add_message_to_gui(f"UNEXPECTED ERROR IN RECEIVER: {e}", tag='white')
                break
        
        if self.connected: 
            self.connected = False 
            self._update_status("RECEIVER ERROR, DISCONNECTED.", "red")
        print("RECEIVER THREAD TERMINATED.")

    def get_my_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('192.254.254.254', 1)) 
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def _add_message_to_gui(self, message, tag='white'):
        if self.root.winfo_exists():
            self.gui_message_buffer.append((message + "\n", tag))
            if not self.gui_update_scheduled:
                self.gui_update_scheduled = True
                self.root.after(10, self.__perform_gui_update)

    def __perform_gui_update(self):
        self.text_area.config(state=tk.NORMAL)
        for text, tag in self.gui_message_buffer:
            self.text_area.insert(tk.END, text, tag)
        self.gui_message_buffer.clear()
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)
        self.gui_update_scheduled = False

    def _on_closing(self):
        self._update_status("CLIENT SHUTDOWN INITIATED...")
        self._disconnect() 
        
        if self.root.winfo_exists():
            self.root.destroy()
        
        sys.exit(0)

class ServerConfigDialog(simpledialog.Dialog):
    def __init__(self, parent, title, mode="add", initial_name="", initial_host="", initial_port=""):
        self.mode = mode
        self.initial_name = initial_name
        self.initial_host = initial_host
        self.initial_port = initial_port
        super().__init__(parent, title)

    def body(self, master):
        master.configure(bg="gray20")
        tk.Label(master, text="Server Name:", bg="gray20", fg="white", font=("Consolas", 10)).grid(row=0, sticky="w", pady=2)
        tk.Label(master, text="Host Address:", bg="gray20", fg="white", font=("Consolas", 10)).grid(row=1, sticky="w", pady=2)
        tk.Label(master, text="Port Number:", bg="gray20", fg="white", font=("Consolas", 10)).grid(row=2, sticky="w", pady=2)

        self.name_entry = tk.Entry(master, width=30, bg="gray30", fg="white", insertbackground="white", font=("Consolas", 10))
        self.host_entry = tk.Entry(master, width=30, bg="gray30", fg="white", insertbackground="white", font=("Consolas", 10))
        self.port_entry = tk.Entry(master, width=30, bg="gray30", fg="white", insertbackground="white", font=("Consolas", 10))

        self.name_entry.grid(row=0, column=1, padx=5, pady=2)
        self.host_entry.grid(row=1, column=1, padx=5, pady=2)
        self.port_entry.grid(row=2, column=1, padx=5, pady=2)

        if self.mode == "update":
            self.name_entry.insert(0, self.initial_name)
            self.host_entry.insert(0, self.initial_host)
            self.port_entry.insert(0, str(self.initial_port))
        
        return self.name_entry

    def buttonbox(self):
        box = tk.Frame(self)
        box.configure(bg="gray20")

        w = tk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE, 
                      bg="gray30", fg="white", font=("Consolas", 10), activebackground="gray40", activeforeground="white")
        w.pack(side=tk.LEFT, padx=5, pady=5)
        w = tk.Button(box, text="Cancel", width=10, command=self.cancel, 
                      bg="gray30", fg="white", font=("Consolas", 10), activebackground="gray40", activeforeground="white")
        w.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

        box.pack()

    def validate(self):
        name = self.name_entry.get().strip()
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()

        if not name or not host or not port_str:
            messagebox.showwarning("Input Error", "All fields must be filled.", parent=self)
            return False
        
        try:
            port = int(port_str)
            if not (1024 <= port <= 65535):
                messagebox.showwarning("Input Error", "Port must be a number between 1024 and 65535.", parent=self)
                return False
        except ValueError:
            messagebox.showwarning("Input Error", "Port must be a valid number.", parent=self)
            return False
        
        self.result = (name, host, port)
        return True

class ContactConfigDialog(simpledialog.Dialog):
    def __init__(self, parent, title, mode="add", initial_name="", initial_ip="", client_instance=None):
        self.mode = mode
        self.initial_name = initial_name
        self.initial_ip = initial_ip
        self.client_instance = client_instance
        super().__init__(parent, title)

    def body(self, master):
        master.configure(bg="gray20")
        tk.Label(master, text="Contact Name:", bg="gray20", fg="white", font=("Consolas", 10)).grid(row=0, sticky="w", pady=2)
        tk.Label(master, text="Contact IP Address:", bg="gray20", fg="white", font=("Consolas", 10)).grid(row=1, sticky="w", pady=2)

        self.name_entry = tk.Entry(master, width=30, bg="gray30", fg="white", insertbackground="white", font=("Consolas", 10))
        self.ip_entry = tk.Entry(master, width=30, bg="gray30", fg="white", insertbackground="white", font=("Consolas", 10))

        self.name_entry.grid(row=0, column=1, padx=5, pady=2)
        self.ip_entry.grid(row=1, column=1, padx=5, pady=2)

        if self.mode == "update":
            self.name_entry.insert(0, self.initial_name)
            self.ip_entry.insert(0, self.initial_ip)
        
        return self.name_entry

    def buttonbox(self):
        box = tk.Frame(self)
        box.configure(bg="gray20")

        w = tk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE, 
                      bg="gray30", fg="white", font=("Consolas", 10), activebackground="gray40", activeforeground="white")
        w.pack(side=tk.LEFT, padx=5, pady=5)
        w = tk.Button(box, text="Cancel", width=10, command=self.cancel, 
                      bg="gray30", fg="white", font=("Consolas", 10), activebackground="gray40", activeforeground="white")
        w.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

        box.pack()

    def validate(self):
        name = self.name_entry.get().strip()
        ip = self.ip_entry.get().strip()

        if not name or not ip:
            messagebox.showwarning("Input Error", "All fields must be filled.", parent=self)
            return False
        
        try:
            socket.inet_aton(ip)
        except socket.error:
            messagebox.showwarning("Input Error", "Invalid IP Address format.", parent=self)
            return False
        
        for contact in self.client_instance.contacts:
            if self.mode == "update" and contact['ip'] == self.initial_ip:
                continue
            
            if contact['name'] == name:
                messagebox.showwarning("Input Error", f"A contact with name '{name}' already exists.", parent=self)
                return False
            if contact['ip'] == ip:
                messagebox.showwarning("Input Error", f"A contact with IP '{ip}' already exists.", parent=self)
                return False
        
        if self.mode == "add" and ip == self.client_instance.FIXED_SERVER_CONTACT_IP:
            messagebox.showwarning("Invalid IP", f"Cannot use reserved IP '{self.client_instance.FIXED_SERVER_CONTACT_IP}' for a new contact.", parent=self)
            return False

        self.result = (name, ip)
        return True

if __name__ == "__main__":
    client = Client()
