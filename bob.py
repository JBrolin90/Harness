import argparse
from session.session_manager import SessionManager
from terminal_history import terminal_history_upgrade
from task.constants import NO_TEXT_RESPONSE
from logger import setup_debug_logging, get_logger

VERSION = "0.3.0"


def main():
    import os
    
    terminal_history_upgrade()

    parser = argparse.ArgumentParser(description="Bob-Harness CLI")
    parser.add_argument(
        "--provider",
        default="cloud-pro",
        help="LLM provider name (default: cloud-pro)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging to harness_debug.log (or HARNESS_DEBUG_LOG env var)"
    )
    args = parser.parse_args()

    # Set up debug logging
    debug_enabled = args.debug or os.environ.get("HARNESS_DEBUG", "0").lower() in ("1", "true", "yes")
    setup_debug_logging(enabled=debug_enabled)
    if debug_enabled:
        log_path = os.environ.get("HARNESS_DEBUG_LOG", "harness_debug.log")
        print(f"[Debug logging enabled: {log_path}]")

    session = SessionManager(args.provider)

    print(f"Bob-Harness v{VERSION} initialized.")
    print("Type 'exit' to quit.")

    while True:
        user_input = input("\nJoachim: ")
        if user_input.lower() == "exit":
            break
        result = session.run_task(user_input)
        if result and result != NO_TEXT_RESPONSE:
            print(f"\nBob: {result}")


if __name__ == "__main__":
    main()