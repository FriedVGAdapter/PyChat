class ClearCommand:
    name = "clear"

    def execute(self, gui, args):
        gui.term_area.configure(state='normal')
        gui.term_area.delete("1.0", "end")
        return None
