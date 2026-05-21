
import readline
import os
import atexit

def terminal_history_upgrade():
    # --- TERMINAL HISTORY UPGRADE ---
    # Explicitly initialize key bindings to force the VS Code terminal to respect it
    readline.parse_and_bind('tab: complete')

    # Create a hidden history file in your home directory
    histfile = os.path.join(os.path.expanduser("~"), ".Bob_harness_history")

    # Load existing history if the file exists
    try:
        readline.read_history_file(histfile)
        readline.set_history_length(1000) # Keep the last 1000 commands
    except FileNotFoundError:
        pass

    # Save the history automatically when you type 'exit' or close the script
    atexit.register(readline.write_history_file, histfile)
