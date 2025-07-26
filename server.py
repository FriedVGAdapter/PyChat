import socket
import threading
import time
import sys
import tkinter as tk
from tkinter import scrolledtext, messagebox, END
import config
import json
import command_loader
import os

class Server:
    def __init__(self, gui):
        self.gui = gui
        self.gui.log_output("Starting Server...")

        self.running = False
        self.connections = {}
        self.client_threads = {}
        self.client_messages = {}
        self.next_client_id = 1

        self.server_socket = None

        self.setup()

    def setup(self):
        if self.running:
            self.gui.log_output("Server is already running.")
            return

        self.running = True

        self.server_thread = threading.Thread(target=self._server_listener_thread)
        self.server_thread.daemon = True
        self.server_thread.start()

        self.gui.log_output("Server listener thread started.")

    def _server_listener_thread(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.gui.config.SERVER_HOST, self.gui.config.SERVER_PORT))
            self.server_socket.listen(5)

            self.gui.log_output(f"Server listening on {self.gui.config.SERVER_HOST}:{self.gui.config.SERVER_PORT}")

            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    client_id = self.next_client_id
                    self.next_client_id += 1
                    client_info = f"Client {client_id} ({addr[0]}:{addr[1]})"

                    self.connections[addr] = conn
                    self.client_messages[addr] = []
                    self.gui.log_output(f"{client_info} connected.")

                    client_handler_thread = threading.Thread(target=self._handle_client_thread, args=(conn, addr, client_info))
                    client_handler_thread.daemon = True
                    client_handler_thread.start()
                    self.client_threads[addr] = client_handler_thread
                except OSError as e:
                    if self.running:
                        self.gui.log_output(f"Accept error: {e}")
                    break
                except Exception as e:
                    self.gui.log_output(f"Unexpected error in accept loop: {e}")
                    break
        except socket.error as e:
            self.gui.log_output(f"Server setup error: {e}")
            self.running = False
        except Exception as e:
            self.gui.log_output(f"General Server Error: {e}")
            self.running = False
        finally:
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
                self.gui.log_output("Server socket closed.")
            self.gui.log_output("Server listener stopped.")

    def _handle_client_thread(self, client_socket, addr, client_info):
        try:
            while self.running and addr in self.connections:
                data = client_socket.recv(8192)
                if not data:
                    self.gui.log_output(f"{client_info} disconnected.")
                    break

                received_raw_message = data.decode('utf-8')
                self.gui.log_output(f"Received from {client_info}: {received_raw_message}")

                sender_ip = addr[0]

                try:
                    parsed_message = json.loads(received_raw_message)

                    msg_type = parsed_message.get("type")
                    message_content = parsed_message.get("message")
                    recipient_ip = parsed_message.get("recipient")

                    parsed_message["sender_ip"] = sender_ip

                    if msg_type == "DM":
                        found_recipient = False
                        for client_addr_tuple, client_conn_socket in list(self.connections.items()):
                            if client_addr_tuple[0] == recipient_ip:
                                try:
                                    forward_json = json.dumps(parsed_message)
                                    client_conn_socket.sendall(forward_json.encode('utf-8'))
                                    self.gui.log_output(f"DM from {sender_ip} to {recipient_ip}: {message_content}")
                                    found_recipient = True
                                    break
                                except socket.error as send_e:
                                    self.gui.log_output(f"Error sending DM to {recipient_ip}: {send_e}")
                                    self._cleanup_disconnected_client(client_addr_tuple)
                        if not found_recipient:
                            error_msg = {"type": "ERROR", "message": f"Recipient {recipient_ip} not found or offline."}
                            self._send_json_to_client(client_socket, error_msg)
                            self.gui.log_output(f"Recipient {recipient_ip} not found for DM from {sender_ip}")

                    elif msg_type == "BROADCAST":
                        forward_json = json.dumps(parsed_message)
                        failed_sends = []
                        for client_addr_tuple, client_conn_socket in list(self.connections.items()):
                            if client_addr_tuple[0] != sender_ip:
                                try:
                                    client_conn_socket.sendall(forward_json.encode('utf-8'))
                                    self.gui.log_output(f"Broadcast from {sender_ip} to {client_addr_tuple[0]}: {message_content}")
                                except socket.error as send_e:
                                    self.gui.log_output(f"Error broadcasting to {client_addr_tuple[0]}: {send_e}")
                                    failed_sends.append(client_addr_tuple)
                        for failed_addr in failed_sends:
                            self._cleanup_disconnected_client(failed_addr)
                        self.gui.log_output(f"Broadcast from {sender_ip}: {message_content}")
                    else:
                        self.gui.log_output(f"Unknown JSON type from {sender_ip}: {msg_type}")
                        error_msg = {"type": "ERROR", "message": f"Unknown message type: {msg_type}"}
                        self._send_json_to_client(client_socket, error_msg)

                except json.JSONDecodeError:
                    self.gui.log_output(f"Non-JSON message from {addr[0]}: {received_raw_message}")
                    error_msg = {"type": "ERROR", "message": "Server expects JSON messages."}
                    self._send_json_to_client(client_socket, error_msg)
                except Exception as e:
                    self.gui.log_output(f"Error processing message from {addr[0]}: {e}")
                    error_msg = {"type": "ERROR", "message": "Server processing error."}
                    self._send_json_to_client(client_socket, error_msg)

        except socket.error as e:
            self.gui.log_output(f"Client handler error for {client_info}: {e}")
        except Exception as e:
            self.gui.log_output(f"Unexpected client handler error for {client_info}: {e}")
        finally:
            self._cleanup_disconnected_client(addr)
            self.gui.log_output(f"Handler for {client_info} terminated.")

    def _cleanup_disconnected_client(self, addr):
        if addr in self.connections:
            try:
                self.connections[addr].shutdown(socket.SHUT_RDWR)
                self.connections[addr].close()
            except OSError as e:
                self.gui.log_output(f"Error closing socket for {addr}: {e}")
            del self.connections[addr]
        if addr in self.client_threads:
            del self.client_threads[addr]
        if addr in self.client_messages:
            del self.client_messages[addr]
        self.gui.log_output(f"Client {addr} cleaned up.")

    def _send_json_to_client(self, client_socket, json_data):
        try:
            json_message = json.dumps(json_data)
            client_socket.sendall(json_message.encode('utf-8'))
        except socket.error as e:
            self.gui.log_output(f"Send error to client: {e}")
        except Exception as e:
            self.gui.log_output(f"Unexpected send error to client: {e}")

    def stop_server(self):
        self.running = False
        if self.server_socket:
            try:
                temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                temp_socket.connect((self.gui.config.SERVER_HOST, self.gui.config.SERVER_PORT))
                temp_socket.close()
            except socket.error as e:
                self.gui.log_output(f"Error unblocking server socket: {e}")
            finally:
                self.server_socket.close()
                self.server_socket = None

        for addr, conn in list(self.connections.items()):
            self._cleanup_disconnected_client(addr)
        self.gui.log_output("Server stopped.")


class ServerGUI:
    def __init__(self):
        self.config = config
        self.root = tk.Tk()
        self.term_area = None
        self.log_area = None
        self.prompt = "> "
        self.command_history = []
        self.history_index = -1
        self._initial_enter_processed = False

        self._setup_gui()
        self.server = Server(self)

        if os.getcwd() not in sys.path:
            sys.path.append(os.getcwd())
        
        self.commands = command_loader.load_commands("commands")
        
        self._terminal_println(f"{config.APP_NAME} [Version: {config.APP_VERSION}]")
        self._terminal_println(f"Made by {config.APP_AUTHOR}")
        self._terminal_println(f"")
        self._terminal_println(f"Enter help for a list of commands")
        self._write_prompt()
        
    def _setup_gui(self):
        self.root.title(f"{self.config.APP_NAME} - Server Manager")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=2)

        self.log_area = scrolledtext.ScrolledText(self.root, bg="black", fg="white", font=("Consolas", 10), wrap=tk.WORD)
        self.log_area.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.log_area.configure(state='disabled')

        self.term_area = scrolledtext.ScrolledText(self.root, bg="#111", fg="#0f0", insertbackground="white", font=("Consolas", 10), wrap=tk.CHAR, insertofftime=0)
        self.term_area.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.term_area.configure(state='normal')

        self.term_area.bind("<Return>", self._on_enter)
        self.term_area.bind("<BackSpace>", self._on_backspace, add="+")
        self.term_area.bind("<Delete>", self._on_delete, add="+")
        self.term_area.bind("<Button-1>", self._on_click_and_focus)
        self.term_area.bind("<Up>", self._history_up)
        self.term_area.bind("<Down>", self._history_down)
        self.term_area.bind("<Key>", self._on_keypress, add="+")


    def log_output(self, message):
        timestamp = time.strftime("[%H:%M:%S] ")
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, timestamp + message + "\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state='disabled')

    def _terminal_println(self, text):
        self.term_area.mark_set(tk.INSERT, tk.END)
        self.term_area.see(tk.END)
        self.term_area.insert(tk.END, text + "\n")
        self.term_area.focus_set()

    def _write_prompt(self):
        self.term_area.mark_set(tk.INSERT, tk.END)
        self.term_area.see(tk.END)
        self.term_area.insert(tk.END, self.prompt)
        self.term_area.mark_set("cmd_start", tk.INSERT)
        self.term_area.focus_set()
    
    def _on_keypress(self, event):
        if event.keysym in ["Return", "BackSpace", "Delete", "Up", "Down", "Left", "Right", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R", "Caps_Lock", "Num_Lock", "Scroll_Lock", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "Home", "End", "Prior", "Next", "Insert", "Print", "Pause", "Menu"]:
            return None 
        
        end_index = self.term_area.index("end-1c")
        line_index = end_index.split('.')[0]

        current_cursor_index = self.term_area.index(tk.INSERT)
        cmd_start_index = f"{line_index}.{len(self.prompt)}"

        if self.term_area.compare(current_cursor_index, "<", cmd_start_index):
            self.term_area.mark_set(tk.INSERT, tk.END)
            self.term_area.see(tk.END)
            return "break"
        
        return None

    def _on_enter(self, event):
        end_index = self.term_area.index("end-1c")
        line_index = end_index.split('.')[0]
        full_line = self.term_area.get(f"{line_index}.0", f"{line_index}.end")
        prompt_len = len(self.prompt)
        command = full_line[prompt_len:].strip()
        
        if not self._initial_enter_processed and not command:
            self._initial_enter_processed = True
            self.term_area.delete("cmd_start", tk.END) 
            self.term_area.insert(tk.END, "\n")
            self._write_prompt()
            return "break"
        
        self._initial_enter_processed = True

        if command and (not self.command_history or self.command_history[-1] != command):
            self.command_history.append(command)
        self.history_index = len(self.command_history)
        
        self.term_area.delete("cmd_start", tk.END)

        self.term_area.insert(tk.END, "\n")

        output = None
        if command:
            output = self._process_command(command)
        else:
            pass

        if output is not None:
            self.term_area.insert(tk.END, f"{output}\n")
        
        self._write_prompt()
        return "break"

    def _on_backspace(self, event):
        current_cursor_index = self.term_area.index(tk.INSERT)
        cmd_start_index = self.term_area.index("cmd_start")
        line_index = current_cursor_index.split('.')[0]

        if self.term_area.compare(current_cursor_index, "<=", f"{line_index}.{len(self.prompt)}"):
            return "break"

        tag_ranges = self.term_area.tag_ranges(tk.SEL)
        if tag_ranges:
            sel_start, sel_end = tag_ranges
            if self.term_area.compare(sel_start, "<", cmd_start_index):
                sel_start = cmd_start_index
            
            if self.term_area.compare(sel_start, "<", sel_end):
                self.term_area.delete(sel_start, sel_end)
            return "break"

        return None

    def _on_delete(self, event):
        current_cursor_index = self.term_area.index(tk.INSERT)
        cmd_start_index = self.term_area.index("cmd_start")

        if self.term_area.compare(current_cursor_index, "<", cmd_start_index):
            return "break"

        if self.term_area.tag_ranges(tk.SEL):
            sel_start, sel_end = self.term_area.tag_ranges(tk.SEL)
            if self.term_area.compare(sel_start, "<", cmd_start_index):
                sel_start = cmd_start_index
            
            if self.term_area.compare(sel_start, "<", sel_end):
                self.term_area.delete(sel_start, sel_end)
            return "break"

        if self.term_area.compare(current_cursor_index, ">=", cmd_start_index) and \
           self.term_area.compare(current_cursor_index, "<", tk.END):
            self.term_area.delete(current_cursor_index)

        return "break"

    def _on_click_and_focus(self, event):
        self.term_area.focus_set()

        if self.term_area.compare("@%d,%d" % (event.x, event.y), "<", "cmd_start"):
            self.term_area.mark_set(tk.INSERT, tk.END)
            self.term_area.see(tk.END)
            return "break"
        return None

    def _history_up(self, event):
        if self.command_history:
            self.history_index -= 1
            if self.history_index < 0:
                self.history_index = 0
            
            self._display_history_command()
        return "break"

    def _history_down(self, event):
        if self.command_history:
            self.history_index += 1
            if self.history_index >= len(self.command_history):
                self.history_index = len(self.command_history)
                self._clear_current_command_line()
            else:
                self._display_history_command()
        return "break"

    def _display_history_command(self):
        current_cursor_index = self.term_area.index(tk.INSERT)
        cmd_start_index = self.term_area.index("cmd_start")
        line_index = current_cursor_index.split('.')[0]

        self.term_area.delete(f"{line_index}.{len(self.prompt)}", tk.END)
        
        if 0 <= self.history_index < len(self.command_history):
            command_to_display = self.command_history[self.history_index]
            self.term_area.insert(tk.END, command_to_display)
        
        self.term_area.mark_set(tk.INSERT, tk.END)
        self.term_area.see(tk.END)
        self.term_area.focus_set()


    def _clear_current_command_line(self):
        self.term_area.delete("cmd_start", tk.END)
        self.term_area.mark_set(tk.INSERT, tk.END)
        self.term_area.see(tk.END)
        self.term_area.focus_set()


    def _process_command(self, command_line):
        if not command_line.strip():
            return None

        parts = command_line.strip().split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1].split() if len(parts) > 1 else []

        cmd = self.commands.get(cmd_name)
        if cmd:
            try:
                return cmd.execute(self, args)
            except Exception as e:
                return f"Error executing command '{cmd_name}': {e}"
        else:
            return f"Unknown command: {cmd_name}"

    def _on_closing(self):
        if self.server:
            self.server.stop_server()
        self.root.destroy()
        sys.exit(0)


if __name__ == '__main__':
    app = ServerGUI()
    app.root.mainloop()
