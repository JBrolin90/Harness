import controller

controller.init()

print(f"Bob-Harness v1.4 initialized. Brain: {controller.current_provider.name} ({controller.current_provider.model})")
print("Type 'exit' to quit.")

while True:
    user_input = input("\nJoachim: ")
    if user_input.lower() == "exit":
        break
    controller.run_task(user_input)