import argparse
import controller

def main():
    parser = argparse.ArgumentParser(description="Bob-Harness CLI")
    parser.add_argument(
        "--provider",
        default="cloud-pro",
        help="LLM provider name (default: cloud-pro)"
    )
    parser.add_argument(
        "--persona",
        default="default",
        help="Persona name (default: default)"
    )
    args = parser.parse_args()

    ctrl = controller.HarnessController(args.provider, args.persona)

    print(f"Bob-Harness v1.5 initialized. \nBrain: \n  {ctrl.current_provider.name} \n  ({ctrl.current_provider.model})")
    print(f"Persona: {ctrl.persona_name}")
    print("Type 'exit' to quit.")

    while True:
        user_input = input("\nJoachim: ")
        if user_input.lower() == "exit":
            break
        ctrl.run_task(user_input)

if __name__ == "__main__":
    main()