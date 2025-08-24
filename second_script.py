import bpy
import re

# =============================================================================
# --- CONFIGURATION: The "Brain" of the Generator ---
# =============================================================================

# Define a default ethnicity in case none is specified in the prompt.
# Capitalization must match the shape key name (e.g., "Caucasian", "Asian").
DEFAULT_ETHNICITY = "Caucasian"

# MAPPING FOR HIGH-LEVEL CONCEPTS (Ethnicity and Fantasy Races)
# The key is the word in the prompt, the value is the text used in the shape key.
CONCEPT_MAP = {
    "caucasian": "Caucasian",
    "asian": "Asian",
    "african": "African",
    "elf": "Elf",
    "dwarf": "Dwarf",
    # Latin and Anime are also in your list, so they can be added here.
}
CONCEPT_SHAPE_KEY_PREFIX = "L1_"


# MAPPING FOR COMPOUND BODY/MUSCLE FEATURES
# Maps a single keyword to multiple shape keys and their values.
# This is for complex terms like "muscular" which means high tone and low mass.
COMPOUND_MAP = {
    "muscular": {
        "L2__{part}_Mass-Tone_min-max": 1.0, # Low Mass, High Tone
    },
    "toned": {
        "L2__{part}_Mass-Tone_min-max": 0.7, # A less extreme version of muscular
    },
    "skinny": {
        "L2__{part}_Mass-Tone_min-min": 0.8, # Low Mass, Low Tone
    },
    "heavy": {
        "L2__{part}_Mass-Tone_max-min": 0.7, # High Mass, Low Tone
    },
    "fat": {
        "L2__{part}_Mass-Tone_max-min": 1.0, # A more extreme version of heavy
    },
    "bulky": {
        "L2__{part}_Mass-Tone_max-max": 0.8, # High Mass, High Tone
    }
}
# A list of body parts that can have the compound keywords above applied to them.
COMPOUND_PARTS = [
    "Abdomen", "Arms_Upperarm", "Arms_Forearm", "Chest", "Legs_Upperlegs", 
    "Legs_Lowerlegs", "Pelvis_Gluteus", "Shoulders"
]


# MAPPING FOR FEATURES AND THEIR MODIFIERS
# The "{ethnicity}" placeholder will be dynamically replaced.
# Shape keys without a placeholder are considered generic and used as-is.
FEATURE_MAP = {
    # -- Face Features --
    "chin": {
        "long": "L2_{ethnicity}_Chin_SizeZ_max",
        "short": "L2_{ethnicity}_Chin_SizeZ_min",
        "wide": "L2_{ethnicity}_Chin_SizeX_max",
        "narrow": "L2_{ethnicity}_Chin_SizeX_min",
        "prominent": "L2_{ethnicity}_Chin_Prominence_max",
        "cleft": "L2_{ethnicity}_Chin_Cleft_max",
    },
    "lips": {
        "full": ["L2_{ethnicity}_Mouth_UpperlipVolume_max", "L2_{ethnicity}_Mouth_LowerlipVolume_max"],
        "thin": ["L2_{ethnicity}_Mouth_UpperlipVolume_min", "L2_{ethnicity}_Mouth_LowerlipVolume_min"],
    },
    "eyes": {
        "big": "L2__Eyes_Size_max",
        "large": "L2__Eyes_Size_max",
        "small": "L2__Eyes_Size_min",
        "wide-set": "L2_{ethnicity}_Eyes_PosX_max",
        "narrow-set": "L2_{ethnicity}_Eyes_PosX_min",
    },
    "nose": {
        "long": "L2_{ethnicity}_Nose_SizeY_max",
        "short": "L2_{ethnicity}_Nose_SizeY_min",
        "wide": "L2_{ethnicity}_Nose_BaseSizeX_max",
        "thin": "L2_{ethnicity}_Nose_BridgeSizeX_min",
        "pointy": "L2_{ethnicity}_Nose_TipSize_min",
        "upturned": "L2_{ethnicity}_Nose_TipAngle_max",
    },
    "jaw": {
        "strong": "L2_{ethnicity}_Jaw_Angle_min",
        "wide": "L2_{ethnicity}_Jaw_ScaleX_max",
        "narrow": "L2_{ethnicity}_Jaw_ScaleX_min",
    },
    "ears": {
        "big": ["L2_{ethnicity}_Ears_SizeX_max", "L2_{ethnicity}_Ears_SizeY_max"],
        "small": ["L2_{ethnicity}_Ears_SizeX_min", "L2_{ethnicity}_Ears_SizeY_min"],
        "pointed": "L2__Fantasy_EarsPointed_max"
    },
    # -- Body Features --
    "shoulders": {
        "broad": "L2__Shoulders_SizeX_max",
        "narrow": "L2__Shoulders_SizeX_min",
    },
    "waist": {
        "wide": "L2__Waist_Size_max",
        "thin": "L2__Waist_Size_min",
        "narrow": "L2__Waist_Size_min",
    },
    "torso": {
        "long": "L2__Torso_Length_max",
        "short": "L2__Torso_Length_min",
    },
    "arms": {
        "long": ["L2__Arms_UpperarmLength_max", "L2__Arms_ForearmLength_max"],
        "short": ["L2__Arms_UpperarmLength_min", "L2__Arms_ForearmLength_min"],
    },
    "legs": {
        "long": ["L2__Legs_UpperlegLength_max", "L2__Legs_LowerlegLength_max"],
        "short": ["L2__Legs_UpperlegLength_min", "L2__Legs_LowerlegLength_min"],
    }
}

# MAPPING FOR INTENSITY AND NEGATION
INTENSITY_MAP = {"slightly": 0.3, "somewhat": 0.5, "very": 0.9, "extremely": 1.0}
NEGATION_WORDS = {"no", "not", "without"}
DEFAULT_VALUE = 0.7

# Create a map of antonyms for handling negation.
ANTONYM_MAP = {
    "long": "short", "short": "long", "wide": "narrow", "narrow": "wide",
    "big": "small", "large": "small", "small": "big", "full": "thin", "thin": "full",
    "broad": "narrow", "pointed": None, "cleft": None, # "None" means just set value to 0
}


# =============================================================================
# --- BLENDER HELPER FUNCTIONS ---
# =============================================================================

def get_object(name="mb_male"):
    """Safely gets the character object from the scene."""
    for obj in bpy.data.objects:
        if obj.name.startswith(name):
            return obj
    return None

def reset_character_shape_keys(obj):
    """Resets all shape key values to 0.0 for a clean start."""
    if not obj or not getattr(obj.data, "shape_keys", None): return
    print("--- Resetting all shape keys ---")
    for kb in obj.data.shape_keys.key_blocks:
        kb.value = 0.0
    print("Reset complete.")

def apply_morph(obj, shape_key_name, value):
    """Applies a single morph value, checking if the key exists."""
    if not obj or not getattr(obj.data, "shape_keys", None): return
    if shape_key_name in obj.data.shape_keys.key_blocks:
        print(f"Applying morph: '{shape_key_name}' with value {value:.2f}")
        obj.data.shape_keys.key_blocks[shape_key_name].value = value
    else:
        print(f"Warning: Shape key '{shape_key_name}' not found.")


# =============================================================================
# --- MAIN LOGIC ---
# =============================================================================

def process_and_apply_prompt(prompt, character_obj):
    """Parses a text prompt and applies the corresponding shape keys."""
    reset_character_shape_keys(character_obj)

    prompt_lower = prompt.lower()
    words = re.findall(r'\b\w+\b', prompt_lower) # Split into words
    
    changes_to_apply = {}
    
    # --- Step 1: Detect Ethnicity/Concept ---
    detected_ethnicity = DEFAULT_ETHNICITY
    for keyword, concept_name in CONCEPT_MAP.items():
        if keyword in words:
            detected_ethnicity = concept_name
            shape_key = f"{CONCEPT_SHAPE_KEY_PREFIX}{concept_name}"
            changes_to_apply[shape_key] = 1.0
            print(f"Detected concept: {detected_ethnicity}")
            break # Stop after finding the first ethnicity

    # --- Step 2: Parse for Compound Keywords (e.g., "muscular body") ---
    for keyword, morphs in COMPOUND_MAP.items():
        if keyword in words:
            # Check if a specific body part is mentioned (e.g. "muscular arms")
            part_mentioned = False
            for i, word in enumerate(words):
                 if keyword == word and i < len(words) - 1:
                     next_word = words[i+1] # e.g., "arms"
                     # Simple check if next word is a known part, can be improved
                     for part in COMPOUND_PARTS:
                         if next_word in part.lower():
                             for template, val in morphs.items():
                                changes_to_apply[template.format(part=part)] = val
                             part_mentioned = True
            # If no specific part is mentioned, apply to the whole body
            if not part_mentioned:
                for part in COMPOUND_PARTS:
                    for template, val in morphs.items():
                        changes_to_apply[template.format(part=part)] = val

    # --- Step 3: Parse for Feature-Modifier Pairs (e.g., "long chin") ---
    for i, word in enumerate(words):
        if word in FEATURE_MAP:  # e.g., found "chin"
            feature_noun = word
            
            # Look at the words before it for modifiers
            if i > 0:
                modifier = words[i-1]
                
                # Handle multi-word modifiers like "wide-set"
                if i > 1 and f"{words[i-2]}-{modifier}" in FEATURE_MAP[feature_noun]:
                    modifier = f"{words[i-2]}-{modifier}"
                    
                if modifier in FEATURE_MAP[feature_noun]:
                    # Determine value and check for negation
                    value = DEFAULT_VALUE
                    is_negated = False
                    
                    # Check for intensity word (e.g. "very")
                    if i > 1 and words[i-2] in INTENSITY_MAP:
                        value = INTENSITY_MAP[words[i-2]]
                        # Check for negation before intensity (e.g. "not very")
                        if i > 2 and words[i-3] in NEGATION_WORDS:
                            is_negated = True
                    # Check for negation directly before modifier (e.g. "not long")
                    elif i > 1 and words[i-2] in NEGATION_WORDS:
                        is_negated = True

                    if is_negated:
                        antonym = ANTONYM_MAP.get(modifier)
                        if antonym: # If an opposite exists (e.g., long -> short)
                            modifier = antonym
                        else: # Otherwise, just set the value to 0
                            value = 0
                            
                    shape_key_templates = FEATURE_MAP[feature_noun][modifier]
                    if not isinstance(shape_key_templates, list):
                        shape_key_templates = [shape_key_templates]
                        
                    for template in shape_key_templates:
                        # DYNAMICALLY build the final shape key name!
                        final_sk_name = template.format(ethnicity=detected_ethnicity)
                        changes_to_apply[final_sk_name] = value

    # --- Step 4: Apply All Detected Changes ---
    print("\n--- Applying detected changes from prompt ---")
    if not changes_to_apply:
        print("No descriptive keywords found in the prompt.")
        return

    for shape_key, value in changes_to_apply.items():
        apply_morph(character_obj, shape_key, value)
        
    bpy.context.view_layer.update()
    print("--- Character generation complete! ---")

# =============================================================================
# --- MAIN EXECUTION BLOCK ---
# =============================================================================

if __name__ == "__main__":
    # === TRY DIFFERENT PROMPTS HERE! ===
    user_prompt = "A very caucasian man with a strong jaw, narrow nose, and small eyes."
#    user_prompt = "An asian man with a pointed nose, full lips, large eyes and a muscular body."
    # user_prompt = "An elf with very long pointed ears and a thin waist."
    # user_prompt = "An asian man with a short chin and not very big eyes."
    
    character = get_object("mb_male")

    if character:
        process_and_apply_prompt(user_prompt, character)
    else:
        print("Error: Could not find an object named 'mb_male'. Check the name in the Outliner.")
