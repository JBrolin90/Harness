import os

def AGENT_md_INGESTIOR():
    agent_file_path = os.path.join(os.getcwd(), "AGENT.md")

    if os.path.exists(agent_file_path):
        print(f"[Harness: Found local AGENT.md in {os.getcwd()}]")
        try:
            with open(agent_file_path, "r") as f:
                return f"\n\n=== DIRECTORY SPECIFIC INSTRUCTIONS (AGENT.md) ===\n{f.read()}\n==================================================\n"
        except Exception as e:
            print(f"[SYSTEM ERROR: Could not read AGENT.md: {str(e)}]")
    else:
        print("[Harness: No AGENT.md found in current directory. Using default persona.]")
    return ""