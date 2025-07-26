class HelpCommand:
    name = "help"

    def execute(self, gui, args):
        commands = gui.commands
        command_names = sorted(commands.keys())
        return "Available commands: " + ", ".join(command_names)
