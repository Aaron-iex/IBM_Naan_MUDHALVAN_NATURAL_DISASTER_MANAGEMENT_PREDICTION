pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 # Adjust cuXXX for your CUDA version
pip install transformers datasets accelerate peft bitsandbytes trl sentencepiece # Add others as needed
pip install huggingface_hub # To interact with Hugging Face Hub
!pip install -q transformers datasets accelerate peft bitsandbytes trl sentencepiece huggingface_hub
python -m venv .venv  # Create a virtual environment named .venv
# Activate it:
# Windows: .\.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -q python-dotenv pandas requests jupyter notebook # Basic tools
