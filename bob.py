import argparse
import controller

def main():
    parser = argparse.ArgumentParser(description="Bob-Harness CLI")
    parser.add_argument(
        "--provider",
        default="cloud-pro",
        help="LLM provider name (default: cloud-pro)"
    )
    args = parser.parse_args()

    ctrl = controller.HarnessController(args.provider)

    print("Bob-Vanilla-Harness v0.1 initialized.")
    print("Type 'exit' to quit.")

    while True:
        user_input = input("\nJoachim: ")
        if user_input.lower() == "exit":
            break
        ctrl.run_task(user_input)

if __name__ == "__main__":
    main()