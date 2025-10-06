import bpy
import sys
import os
from pathlib import Path

# This script is executed directly by the Blender executable.
# Its purpose is to correctly import and start the monitoring loop
# defined in your main 'blender_bridge.py' script.

# 1. Determine the path of the 'blender_bridge.py' script.
# We assume it is in the same directory as this 'blender_startup.py' file.
current_dir = Path(os.path.abspath(__file__)).parent
bridge_script_path = current_dir / "blender_bridge.py"

# 2. Add the script directory to the Blender Python path for importing
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

print(f"Blender Startup: Loading bridge script from {bridge_script_path}")

# 3. Load and execute the bridge script logic
try:
    if not bridge_script_path.exists():
        raise FileNotFoundError(f"blender_bridge.py not found at {bridge_script_path}")

    # Read and execute the blender_bridge.py content
    with open(bridge_script_path, 'r') as f:
        # Use exec to run the script contents, defining functions like start_bridge_monitoring
        exec(f.read())
    
    # Check if the main monitoring function was successfully defined
    if 'start_bridge_monitoring' in locals():
        # Call the function to start the timer loop within Blender
        start_bridge_monitoring()
        print("=== BLENDER BRIDGE AUTO-STARTED SUCCESSFULLY ===")
    else:
        print("Error: start_bridge_monitoring function not found after execution.")

except Exception as e:
    # This catches errors that occur during the loading of blender_bridge.py
    print(f"CRITICAL ERROR: Failed to load or execute blender_bridge.py: {e}")
    # Optional: Exit Blender if the bridge script fails to load
    # bpy.ops.wm.quit_blender()
