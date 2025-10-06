from flask import Flask, render_template, request, jsonify
import json
import os
import time
import subprocess
import sys
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

# =============================================================================
# CONFIGURATION - UPDATE THESE PATHS FOR YOUR SETUP
# =============================================================================

# Communication directory
COMMUNICATION_DIR = os.path.join(os.getcwd(), "blender_bridge")

REQUEST_FILE = os.path.join(COMMUNICATION_DIR, "character_request.json")
RESPONSE_FILE = os.path.join(COMMUNICATION_DIR, "character_response.json")
BLENDER_STATUS_FILE = os.path.join(COMMUNICATION_DIR, "blender_status.json")

# Blender configuration
# >>> VERIFY AND UPDATE THIS PATH! <<<
# Using Blender 4.3 as specified in your last request
BLENDER_EXECUTABLE = r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"

# Your model file
MODEL_BLEND_FILE = r"D:\sem\char-morphing-scripts\base.blend"

# Static startup script path (NEW: This file will execute the bridge script)
BLENDER_STARTUP_SCRIPT = os.path.join(os.getcwd(), "blender_startup.py")

# Bridge script path (for reference only, the startup script uses it)
BRIDGE_SCRIPT_PATH = os.path.join(os.getcwd(), "blender_bridge.py")

# Global state tracking
blender_started_once = False
last_successful_generation = None

# Ensure communication directory exists
os.makedirs(COMMUNICATION_DIR, exist_ok=True)

# =============================================================================
# BLENDER MANAGEMENT FUNCTIONS
# =============================================================================

def is_blender_responsive():
    """Check if Blender can respond to requests (more lenient check)."""
    global last_successful_generation
    
    if not blender_started_once:
        return False
    
    try:
        # Check if a response file exists from a previous request
        if os.path.exists(RESPONSE_FILE):
            # This is a very quick check, if it exists, Blender is likely running
            return True

        # Send a quick test request
        test_request = {
            "timestamp": datetime.now().isoformat(),
            "prompt": "__STATUS_CHECK__",
            "status": "pending"
        }
        
        with open(REQUEST_FILE, 'w') as f:
            json.dump(test_request, f)
        
        start_time = time.time()
        while time.time() - start_time < 3: # 3 second timeout
            if os.path.exists(RESPONSE_FILE):
                os.remove(RESPONSE_FILE)
                return True
            time.sleep(0.1)
        
        if os.path.exists(REQUEST_FILE):
            os.remove(REQUEST_FILE)
            
    except Exception as e:
        print(f"Error checking Blender responsiveness: {e}")
    
    return False

def start_blender_with_model():
    """
    Start Blender using the static startup script to load the bridge logic.
    This replaces the dynamic f-string generation and temporary file writing.
    """
    global blender_started_once

    # Absolute paths are more reliable
    model_path = os.path.abspath(MODEL_BLEND_FILE)
    startup_script_path = os.path.abspath(BLENDER_STARTUP_SCRIPT) # Use the static path

    if not os.path.exists(model_path):
        return {"success": False, "error": f"Model file not found: {model_path}"}

    if not os.path.exists(BLENDER_EXECUTABLE):
        return {"success": False, "error": f"Blender executable not found: {BLENDER_EXECUTABLE}"}
    
    # Check for the NEW static startup file
    if not os.path.exists(startup_script_path):
        return {"success": False, "error": f"Static startup script not found: {startup_script_path}. Please create the 'blender_startup.py' file."}

    try:
        # Define the command using the static startup script path
        cmd = [
            BLENDER_EXECUTABLE,
            model_path,
            "--python", startup_script_path, # Direct execution of the static file
            "--background",
        ]

        print(f"Starting Blender with command: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )

        time.sleep(2)
        if process.poll() is not None:
            # If Blender terminated immediately, capture and report the error output
            stdout, stderr = process.communicate()
            return {"success": False, "error": f"Blender process terminated immediately. Check Blender's security settings for running scripts. STDOUT: {stdout.decode()} STDERR: {stderr.decode()}"}

        blender_started_once = True

        return {
            "success": True,
            "message": f"Blender started with {os.path.basename(MODEL_BLEND_FILE)}",
            "process_id": process.pid
        }
    except Exception as e:
        # This catches errors like File Not Found (if BLENDER_EXECUTABLE was wrong) or permission issues.
        return {"success": False, "error": f"Failed to start Blender: {str(e)}"}

# =============================================================================
# FLASK ROUTES (Unchanged)
# =============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start-blender', methods=['POST'])
def start_blender():
    if is_blender_responsive():
        return jsonify({"success": True, "message": "Blender is already running and responsive!"})
    
    result = start_blender_with_model()
    # Ensure a proper 500 status code is returned on failure
    return jsonify(result) if result["success"] else (jsonify(result), 500)

@app.route('/generate', methods=['POST'])
def generate_character():
    global last_successful_generation
    
    try:
        prompt = request.json.get('prompt', '')
        
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
        
        if not blender_started_once:
            return jsonify({
                "error": "Please start Blender first using the 'Start Blender' button."
            }), 400
        
        if os.path.exists(REQUEST_FILE):
            os.remove(REQUEST_FILE)
            time.sleep(0.1)

        request_data = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "status": "pending"
        }
        
        with open(REQUEST_FILE, 'w') as f:
            json.dump(request_data, f)
        
        timeout = 30
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if os.path.exists(RESPONSE_FILE):
                try:
                    with open(RESPONSE_FILE, 'r') as f:
                        response_data = json.load(f)
                    
                    os.remove(RESPONSE_FILE)
                    last_successful_generation = datetime.now()
                    
                    return jsonify({
                        "success": True,
                        "message": "Character generated successfully!",
                        "details": response_data
                    })
                except json.JSONDecodeError:
                    return jsonify({
                        "success": False,
                        "error": "Failed to parse Blender's response file. It may be corrupted."
                    }), 500
            
            time.sleep(0.5)
        
        return jsonify({
            "error": "Timeout waiting for Blender response. Blender might be busy or closed."
        }), 408
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/status')
def status():
    return jsonify({
        "blender_running": is_blender_responsive(),
        "blender_started_once": blender_started_once,
        "model_file": os.path.abspath(MODEL_BLEND_FILE),
        "model_exists": os.path.exists(MODEL_BLEND_FILE),
        "blender_executable": BLENDER_EXECUTABLE,
        "blender_exists": os.path.exists(BLENDER_EXECUTABLE),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/reset-status', methods=['POST'])
def reset_status():
    global blender_started_once, last_successful_generation
    blender_started_once = False
    last_successful_generation = None
    if os.path.exists(REQUEST_FILE): os.remove(REQUEST_FILE)
    if os.path.exists(RESPONSE_FILE): os.remove(RESPONSE_FILE)
    return jsonify({"success": True, "message": "Status reset. You can now start Blender again."})

@app.route('/config')
def config():
    return jsonify({
        "model_file": os.path.abspath(MODEL_BLEND_FILE),
        "blender_executable": BLENDER_EXECUTABLE,
        "communication_dir": os.path.abspath(COMMUNICATION_DIR)
    })

if __name__ == '__main__':
    print("🎭 Character Generator Frontend Starting...")
    print(f"📁 Communication directory: {os.path.abspath(COMMUNICATION_DIR)}")
    print(f"🎨 Model file: {os.path.abspath(MODEL_BLEND_FILE)}")
    print(f"🔧 Blender executable: {BLENDER_EXECUTABLE}")
    print("🌐 Open http://127.0.0.1:5000 in your browser")
    print("🚀 Click 'Start Blender' once, then generate as many characters as you want!")
    
    app.run(debug=True, host='127.0.0.1', port=5000)
