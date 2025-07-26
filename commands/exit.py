class ExitCommand:
    name = "exit"

    def execute(self, gui, args):
        gui.log_output("Shutting down server...")
        gui.root.after(100, gui._on_closing)
        return None
    