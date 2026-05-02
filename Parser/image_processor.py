import torch
from transformers import VisionEncoderDecoderModel, ViTImageProcessor, AutoTokenizer
from PIL import Image
import io

class ImageCaptioner:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ImageCaptioner, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.model_name = "nlpconnect/vit-gpt2-image-captioning"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # CPU generally requires float32 or bfloat16. GPU can use float16.
        # We use float32 by default for compatibility, but the weight file is cached.
        self.torch_dtype = torch.float32 
        
        print(f"Loading Image Captioner ({self.model_name}) on {self.device}...")
        try:
            self.model = VisionEncoderDecoderModel.from_pretrained(self.model_name).to(self.device)
            self.feature_extractor = ViTImageProcessor.from_pretrained(self.model_name)
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._initialized = True
        except Exception as e:
            print(f"Error loading model: {e}")
            self._initialized = False

    def describe_image(self, image_bytes):
        if not self._initialized:
            return "[IMAGE CAPTIONER NOT INITIALIZED]"
            
        if not image_bytes:
            return "[IMAGE DATA MISSING]"
            
        try:
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != "RGB":
                image = image.convert(mode="RGB")

            pixel_values = self.feature_extractor(images=[image], return_tensors="pt").pixel_values
            pixel_values = pixel_values.to(self.device)

            # Generate caption
            output_ids = self.model.generate(
                pixel_values, 
                max_length=20, 
                num_beams=4,
                early_stopping=True
            )
            
            preds = self.tokenizer.batch_decode(output_ids, skip_special_tokens=True)
            caption = preds[0].strip()
            
            # Ensure it's a one-liner
            return caption.capitalize()
        except Exception as e:
            return f"[CAPTION ERROR: {str(e)}]"
