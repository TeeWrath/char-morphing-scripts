import bpy
import re
# This is the "brain" of your script. You will need to expand this
# dictionary with more keywords and corresponding shape keys.

# MAPPING FOR HIGH-LEVEL CONCEPTS (like ethnicity)
ethnicity_map = {
    "caucasian": "L1_Caucasian",
    "asian": "L1_Asian",
    "african": "L1_African",
    # ... add other L1 types like "elf", "dwarf", etc.
}

# MAPPING FOR FEATURES AND THEIR MODIFIERS
# Structure: "feature_noun": {"modifier_adjective": "shape_key_name"}
feature_map = {
    "chin": {
        "long": "L2_Caucasian_Chin_SizeZ_max",
        "short": "L2_Caucasian_Chin_SizeZ_min",
        "wide": "L2_Caucasian_Chin_SizeX_max",
        "narrow": "L2_Caucasian_Chin_SizeX_min",
        "prominent": "L2_Caucasian_Chin_Prominence_max",
    },
    "lips": {
        "full": ["L2_Caucasian_Mouth_UpperlipVolume_max", "L2_Caucasian_Mouth_LowerlipVolume_max"],
        "thin": ["L2_Caucasian_Mouth_UpperlipVolume_min", "L2_Caucasian_Mouth_LowerlipVolume_min"],
    },
    "eyes": {
        "big": "L2__Eyes_Size_max",
        "large": "L2__Eyes_Size_max", # synonym for big
        "small": "L2__Eyes_Size_min",
        "wide": "L2_Caucasian_Eyes_PosX_max", # For wide-set eyes
        "narrow": "L2_Caucasian_Eyes_PosX_min", # For narrow-set eyes
    },
    "nose": {
        "long": "L2_Caucasian_Nose_SizeY_max",
        "short": "L2_Caucasian_Nose_SizeY_min",
        "wide": "L2_Caucasian_Nose_BaseSizeX_max",
        "thin": "L2_Caucasian_Nose_BridgeSizeX_min",
    }
    # ... Continue adding more features like "jaw", "cheeks", "forehead", etc.
}

# MAPPING FOR INTENSITY MODIFIERS
# This allows for phrases like "very long" or "slightly big"
intensity_map = {
    "slightly": 0.3,
    "somewhat": 0.5,
    "very": 0.9,
    "extremely": 1.0,
}
DEFAULT_VALUE = 0.7 # Default value if no intensity word is found

# --- Helper Functions ---

def get_object(name="mb_male"):
    """Safely gets the character object from the scene."""
    # Note: The object might have a different name like "mb_male.001"
    # This code finds the object that starts with the base name.
    for obj in bpy.data.objects:
        if obj.name.startswith(name):
            return obj
    return None

def reset_character_shape_keys(obj):
    """Resets all shape key values to 0.0 for a clean start."""
    if not obj or not getattr(obj.data, "shape_keys", None):
        return
        
    print("--- Resetting all shape keys ---")
    for kb in obj.data.shape_keys.key_blocks:
        kb.value = 0.0
    print("Reset complete.")

def apply_morph(obj, shape_key_name, value):
    """Applies a single morph value to a given shape key."""
    if not obj or not getattr(obj.data, "shape_keys", None):
        return

    if shape_key_name in obj.data.shape_keys.key_blocks:
        print(f"Applying morph: '{shape_key_name}' with value {value:.2f}")
        obj.data.shape_keys.key_blocks[shape_key_name].value = value
    else:
        print(f"Warning: Shape key '{shape_key_name}' not found on object.")


# --- Main Logic Function ---

def process_and_apply_prompt(prompt, character_obj):
    """
    Parses a text prompt and applies the corresponding shape keys to the character.
    """
    # First, reset the character to a neutral state
    reset_character_shape_keys(character_obj)

    # Clean the prompt by making it lowercase
    prompt_lower = prompt.lower()
    
    # Store the changes we want to make
    changes_to_apply = {}

    # --- Step 2: Parse and Map ---

    # Part A: Handle high-level concepts like ethnicity
    for keyword, shape_key in ethnicity_map.items():
        if keyword in prompt_lower:
            changes_to_apply[shape_key] = 1.0 # Ethnicity is usually all or nothing

    # Part B: Handle feature-modifier pairs (e.g., "long chin")
    words = prompt_lower.split()
    for i, word in enumerate(words):
        if word in feature_map: # e.g., found "chin"
            # Now look at the word before it to find the modifier (e.g., "long")
            if i > 0:
                modifier = words[i-1]
                if modifier in feature_map[word]:
                    shape_keys = feature_map[word][modifier]
                    
                    # Determine the value based on intensity
                    value = DEFAULT_VALUE
                    # Check for an intensity word before the modifier (e.g., "very" long chin)
                    if i > 1 and words[i-2] in intensity_map:
                        value = intensity_map[words[i-2]]
                    
                    # Handle cases where one keyword maps to multiple shape keys (like "full lips")
                    if isinstance(shape_keys, list):
                        for sk in shape_keys:
                            changes_to_apply[sk] = value
                    else: # It's a single shape key
                        changes_to_apply[shape_keys] = value

    # --- Step 3: Apply All Mapped Values ---
    print("\n--- Applying detected changes from prompt ---")
    if not changes_to_apply:
        print("No descriptive keywords found in the prompt.")
        return

    for shape_key, value in changes_to_apply.items():
        apply_morph(character_obj, shape_key, value)
        
    # Finally, update the viewport so we can see the changes
    bpy.context.view_layer.update()
    print("--- Character generation complete! ---")


# --- Main Execution Block ---

if __name__ == "__main__":
    # The user's text-based description
    user_prompt = "make a very asian face with a long chin, full lips and very small eyes."
    
    # Get the character object
    character = get_object("mb_male")

    if character:
        process_and_apply_prompt(user_prompt, character)
    else:
        print("Error: Could not find an object named 'mb_male'. Please check the name in the Outliner.")
