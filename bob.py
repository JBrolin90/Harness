import controller

ctrl = controller.HarnessController()

print(f"Bob-Harness v1.5 initialized. \nBrain: \n  {ctrl.current_provider.name} \n  ({ctrl.current_provider.model})")
print("Type 'exit' to quit.")

while True:
    user_input = input("\nJoachim: ")
    if user_input.lower() == "exit":
        break
    ctrl.run_task(user_input)