# ClientCommand
# Version: 1.0.0
# Works with server version 1.0.0

class ClientCommand:
    name = "client"

    def __init__(self) -> None:
        self.command = "client"
        self.gui = None
        self.args = None

        self.subcommands = [
            ("connected_client_amount", "Shows the number of connected clients"),
            ("list_clients", "Lists all connected clients"),
            ("disconnect_client <ip>", "Disconnects a client by IP address"),
            ("client_info <ip>", "Shows information about a specific client"),
        ]

        self.valid_subcommands = {subcmd.split()[0] for subcmd, _ in self.subcommands}

    def execute(self, gui, args):
        self.gui = gui
        self.args = args

        if len(self.args) == 0:
            self._show_usage()
            return None

        subcommand = self.args[0]
        sub_args = self.args[1:]

        if subcommand not in self.valid_subcommands:
            gui._terminal_println(f"Error: Unknown subcommand '{subcommand}'")
            self._show_usage()
            return None

        # Dispatch to subcommand handler
        if subcommand == "connected_client_amount":
            self._connected_client_amount()
        elif subcommand == "list_clients":
            self._list_clients()
        elif subcommand == "disconnect_client":
            self._disconnect_client(sub_args)
        elif subcommand == "client_info":
            self._client_info(sub_args)
        else:
            gui._terminal_println(f"Error: Subcommand '{subcommand}' not implemented.")
        return None

    def _show_usage(self):
        self.gui._terminal_println("Usage:")
        self.gui._terminal_println("")
        self.gui._terminal_println(f"{self.command} [SUBCOMMAND]")
        self.gui._terminal_println("")
        for subcmd, desc in self.subcommands:
            self.gui._terminal_println(f"    {subcmd.ljust(27)}-> {desc}")

    def _connected_client_amount(self):
        """Shows the number of currently connected clients."""
        num_clients = len(self.gui.server.connections)
        self.gui._terminal_println(f"Currently connected clients: {num_clients}")

    def _list_clients(self):
        """Lists all connected clients by their IP:Port address."""
        if not self.gui.server.connections:
            self.gui._terminal_println("No clients currently connected.")
            return

        self.gui._terminal_println("Connected Clients:")
        for addr_tuple in self.gui.server.connections.keys():
            self.gui._terminal_println(f"  - {addr_tuple[0]}:{addr_tuple[1]}")

    def _disconnect_client(self, sub_args):
        """Disconnects a client by its IP address."""
        if not sub_args:
            self.gui._terminal_println("Usage: client disconnect_client <ip>")
            return

        target_ip = sub_args[0]
        found_client = False
        client_to_disconnect_addr = None

        # Find the full address tuple for the given IP
        for addr_tuple in self.gui.server.connections.keys():
            if addr_tuple[0] == target_ip:
                client_to_disconnect_addr = addr_tuple
                found_client = True
                break
        
        if found_client:
            self.gui._terminal_println(f"Attempting to disconnect client {target_ip}...")
            # Call the server's internal cleanup method
            self.gui.server._cleanup_disconnected_client(client_to_disconnect_addr)
            self.gui._terminal_println(f"Client {target_ip} disconnected (if it was connected).")
        else:
            self.gui._terminal_println(f"Error: Client with IP '{target_ip}' not found.")

    def _client_info(self, sub_args):
        """Shows information about a specific client by its IP address."""
        if not sub_args:
            self.gui._terminal_println("Usage: client client_info <ip>")
            return

        target_ip = sub_args[0]
        found_client = False
        
        for addr_tuple in self.gui.server.connections.keys():
            if addr_tuple[0] == target_ip:
                self.gui._terminal_println(f"Information for client {target_ip}:")
                self.gui._terminal_println(f"  - Full Address: {addr_tuple[0]}:{addr_tuple[1]}")
                # You could add more info here if the server stored it, e.g.,
                # self.gui._terminal_println(f"  - Messages Received: {len(self.gui.server.client_messages.get(addr_tuple, []))}")
                # self.gui._terminal_println(f"  - Handler Thread Alive: {self.gui.server.client_threads.get(addr_tuple).is_alive()}")
                found_client = True
                break
        
        if not found_client:
            self.gui._terminal_println(f"Error: Client with IP '{target_ip}' not found or is not connected.")