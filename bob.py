import argparse
from controller import HarnessController
from terminal_history import terminal_history_upgrade

VERSION = "0.3.0"

def main():
    terminal_history_upgrade()
    
    parser = argparse.ArgumentParser(description="Bob-Harness CLI")
    parser.add_argument(
        "--provider",
        default="cloud-pro",
        help="LLM provider name (default: cloud-pro)"
    )
    args = parser.parse_args()

    ctrl = HarnessController(args.provider)

    print(f"Bob-Harness v{VERSION} initialized.")
    print("Type 'exit' to quit.")

    while True:
        user_input = input("\nJoachim: ")
        if user_input.lower() == "exit":
            break
        ctrl.run_task(user_input)

if __name__ == "__main__":
    main()