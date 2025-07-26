import importlib
import os

def load_commands(command_folder="commands"):
    commands = {}
    for filename in os.listdir(command_folder):
        if filename.endswith(".py") and filename != "__init__.py":
            modulename = filename[:-3]
            module = importlib.import_module(f"{command_folder}.{modulename}")

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type) and
                    hasattr(attr, "name") and
                    callable(getattr(attr, "execute", None))
                ):
                    cmd_instance = attr()
                    commands[cmd_instance.name] = cmd_instance
    return commands
