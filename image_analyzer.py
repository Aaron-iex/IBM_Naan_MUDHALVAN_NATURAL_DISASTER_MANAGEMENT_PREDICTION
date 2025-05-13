# image_analyzer.py
# Place this in your project root

import os
import logging
import json
import httpx # For fetching image from URL asynchronously

# --- Attempt to import TensorFlow ---
try:
    import tensorflow as tf
    # from tensorflow.keras.preprocessing import image # Keras preprocessing utilities (use tf.keras.utils for newer TF)
    from tensorflow.keras.utils import img_to_array # Updated import
    import numpy as np
    from PIL import Image 
    import io 
    TF_KERAS_AVAILABLE = True
    logger_img = logging.getLogger(__name__ + "_tf") # Separate logger for TF messages
    logger_img.info("TensorFlow and Pillow imported successfully for image_analyzer.")
except ImportError:
    TF_KERAS_AVAILABLE = False
    # This warning will be logged by the main app's logger if this module is imported
    # print("Warning: TensorFlow/Keras or Pillow not installed. CNN functionality will be disabled.")

# Use the main app's logger if available, otherwise create a default one
# This allows logs from this module to appear alongside FastAPI logs when run via Uvicorn.
# If run standalone, it will create a default logger.
logger = logging.getLogger(__name__)
if not logger.hasHandlers(): # Avoid adding multiple handlers if already configured
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')


# --- Global variable for the loaded model and class labels ---
cnn_model = None
class_labels = None 
MODEL_INPUT_SHAPE = (224, 224) # Example: (height, width) - Must match your trained model's input

# --- Path to your trained model and class labels ---
# Assumes an 'ml_models' subfolder in the same directory as this script (project root)
BASE_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ml_models')
MODEL_PATH_TF = os.path.join(BASE_MODEL_DIR, 'final_cyclone_detector_cnn.keras') # Use .keras for TF 2.x+
CLASS_LABELS_PATH = os.path.join(BASE_MODEL_DIR, 'cnn_class_labels.json')

def load_cnn_model():
    """
    Loads the pre-trained CNN model and class labels from disk.
    Returns True if successful, False otherwise.
    """
    global cnn_model, class_labels
    if cnn_model is not None and class_labels is not None:
        logger.info("CNN model and labels already loaded.")
        return True

    if not TF_KERAS_AVAILABLE:
        logger.error("TensorFlow/Keras is not available. Cannot load CNN model.")
        return False

    # Create ml_models directory if it doesn't exist (for initial setup)
    if not os.path.exists(BASE_MODEL_DIR):
        try:
            os.makedirs(BASE_MODEL_DIR)
            logger.info(f"Created directory: {BASE_MODEL_DIR}")
        except Exception as e:
            logger.error(f"Could not create directory {BASE_MODEL_DIR}: {e}")
            return False # Cannot proceed if model directory can't be accessed/created

    try:
        if os.path.exists(MODEL_PATH_TF):
            cnn_model = tf.keras.models.load_model(MODEL_PATH_TF)
            logger.info(f"TensorFlow/Keras CNN model loaded successfully from: {MODEL_PATH_TF}")
            
            if os.path.exists(CLASS_LABELS_PATH):
                with open(CLASS_LABELS_PATH, 'r') as f:
                    class_labels = json.load(f)
                logger.info(f"CNN class labels loaded: {class_labels}")
                if not isinstance(class_labels, list) or not all(isinstance(label, str) for label in class_labels):
                    logger.error("Class labels file is not a valid list of strings.")
                    class_labels = None # Invalidate if format is wrong
                    return False
                if cnn_model.output_shape[-1] != 1 and len(class_labels) != cnn_model.output_shape[-1]: # Check for multi-class
                    logger.error(f"Mismatch between model output units ({cnn_model.output_shape[-1]}) and number of class labels ({len(class_labels)}).")
                    class_labels = None
                    return False
                elif cnn_model.output_shape[-1] == 1 and len(class_labels) != 2: # Check for binary
                    logger.error(f"For binary classification (1 output unit), class_labels should have 2 entries (e.g., ['negative_class', 'positive_class']). Found: {len(class_labels)}")
                    class_labels = None
                    return False

                return True
            else:
                logger.error(f"CNN class labels file not found at {CLASS_LABELS_PATH}. Prediction interpretation will be limited.")
                return False # Model is useless without knowing what the output means
        else:
            logger.warning(f"CNN model file not found at {MODEL_PATH_TF}. Place your trained .keras model there.")
            return False
    except Exception as e:
        logger.error(f"Error loading TensorFlow/Keras CNN model or labels: {e}", exc_info=True)
        cnn_model = None
        class_labels = None
        return False

def preprocess_image_for_cnn(image_bytes: bytes):
    """Preprocesses image bytes for the loaded TensorFlow/Keras CNN model."""
    if not TF_KERAS_AVAILABLE: 
        logger.warning("TensorFlow not available for preprocessing.")
        return None
    try:
        # Open image using Pillow
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB') 
        # Resize to the target shape your model expects
        img = img.resize((MODEL_INPUT_SHAPE[1], MODEL_INPUT_SHAPE[0])) # PIL uses (width, height)
        
        # Convert PIL image to NumPy array
        img_array = img_to_array(img) # tf.keras.utils.img_to_array
        
        # Expand dimensions to create a batch of 1 image
        img_array = np.expand_dims(img_array, axis=0)
        
        # Normalize pixel values if your model was trained with normalization (e.g., / 255.0)
        img_array = img_array / 255.0 
        
        return img_array
    except Exception as e:
        logger.error(f"Error preprocessing image for CNN: {e}", exc_info=True)
        return None

async def analyze_satellite_image(image_url: str, client: httpx.AsyncClient):
    """
    Fetches an image from a URL and analyzes it using the loaded CNN model.
    Returns a dictionary with 'prediction_label' and 'confidence' or 'error'.
    """
    if not cnn_model or not class_labels:
        logger.warning("analyze_satellite_image called but CNN model or labels are not loaded.")
        # Attempt to load them if not already loaded (e.g., if startup event failed or was skipped)
        if not load_cnn_model():
            return {"error": "CNN model/labels not available or failed to load."}
    
    logger.info(f"Fetching image for CNN analysis from: {image_url}")
    try:
        response = await client.get(image_url, timeout=20.0, follow_redirects=True)
        response.raise_for_status()
        image_bytes = response.content
    except httpx.RequestError as e:
        logger.error(f"HTTP error fetching image {image_url} for CNN: {e}")
        return {"error": f"Failed to fetch image from URL: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error fetching image {image_url}: {e}", exc_info=True)
        return {"error": f"Unexpected error fetching image: {e}"}

    processed_img = preprocess_image_for_cnn(image_bytes)
    if processed_img is None:
        return {"error": "Image preprocessing failed for CNN model."}
    
    try:
        logger.info("Making prediction with CNN model...")
        prediction_scores_batch = cnn_model.predict(processed_img)
        prediction_scores = prediction_scores_batch[0] # Get scores for the single image in the batch
        
        # Interpret prediction based on model output shape and class labels
        if cnn_model.output_shape[-1] == 1: # Binary classification with sigmoid output
            # Assumes class_labels = ['negative_class_name', 'positive_class_name']
            # e.g., ['no_cyclone_visible', 'cyclone_visible']
            score = float(prediction_scores[0])
            if score > 0.5: # Threshold for positive class
                predicted_label = class_labels[1] 
                confidence = score
            else:
                predicted_label = class_labels[0]
                confidence = 1.0 - score
            all_scores_dict = {class_labels[0]: round(1.0 - score, 3), class_labels[1]: round(score, 3)}

        elif len(class_labels) == cnn_model.output_shape[-1]: # Multi-class classification with softmax
            predicted_class_index = np.argmax(prediction_scores)
            confidence = float(prediction_scores[predicted_class_index])
            predicted_label = class_labels[predicted_class_index]
            all_scores_dict = {label: round(float(score), 3) for label, score in zip(class_labels, prediction_scores)}
        else:
            logger.error("Mismatch between model output and class_labels for score interpretation.")
            return {"error": "CNN output interpretation error due to label mismatch."}

        logger.info(f"CNN Prediction: {predicted_label}, Confidence: {confidence:.3f}")
        return {
            "prediction_label": predicted_label, 
            "confidence": round(confidence, 3),
            "all_scores": all_scores_dict # Provides scores for all classes
        }
    except Exception as e:
        logger.error(f"Error during CNN prediction: {e}", exc_info=True)
        return {"error": f"CNN prediction failed: {e}"}

# Optional: Attempt to load the model when this module is first imported.
# This is also called during FastAPI startup.
# if TF_KERAS_AVAILABLE:
#    load_cnn_model()
