export interface MorphTarget {
  name: string;
  index: number;
  value: number;
}

export interface MorphCategory {
  name: string;
  targets: MorphTarget[];
  expanded: boolean;
}

export interface MorphState {
  [targetName: string]: number;
}

export const CATEGORY_KEYWORDS: Record<string, string[]> = {
  "Macro": [
    "gender", "male", "female", "age", "baby", "child", "teen", "young", "old",
    "weight", "thin", "fat", "overweight", "muscle", "height", "tall", "short",
    "proportion", "caucasian", "african", "asian", "ethnicity", "race",
    "macrodetail", "macro",
  ],
  "Head": [
    "head-", "head_", "skull", "cranium",
  ],
  "Forehead": [
    "forehead", "brow-",
  ],
  "Eyes": [
    "eye-", "eye_", "eyes-", "eyes_", "eyelid", "eyebrow", "iris", "pupil",
  ],
  "Nose": [
    "nose-", "nose_", "nostril", "nasal",
  ],
  "Mouth": [
    "mouth-", "mouth_", "lip-", "lip_", "lips",
  ],
  "Chin": [
    "chin-", "chin_",
  ],
  "Jaw": [
    "jaw-", "jaw_",
  ],
  "Ears": [
    "ear-", "ear_", "ears-", "ears_",
  ],
  "Cheeks": [
    "cheek-", "cheek_", "cheeks",
  ],
  "Neck": [
    "neck-", "neck_",
  ],
  "Torso": [
    "torso", "chest", "breast", "stomach", "belly", "waist", "hip",
    "pelvis", "trunk", "back-", "back_", "spine",
  ],
  "Arms": [
    "arm-", "arm_", "arms", "shoulder", "elbow", "wrist", "forearm",
    "upperarm", "bicep", "tricep",
  ],
  "Hands": [
    "hand-", "hand_", "hands", "finger", "thumb", "palm", "knuckle",
  ],
  "Legs": [
    "leg-", "leg_", "legs", "thigh", "knee", "calf", "shin",
    "ankle", "quadricep", "hamstring",
  ],
  "Feet": [
    "foot", "feet", "toe-", "toe_", "toes", "heel", "arch",
  ],
  "Expressions": [
    "express", "smile", "frown", "angry", "sad", "happy", "surprise",
    "disgust", "fear", "contempt", "blink", "squint", "sneer", "puff",
  ],
};
