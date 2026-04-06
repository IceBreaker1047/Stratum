import torch
import torch.nn as nn
from PIL import Image, ImageOps
import torchvision.transforms as transforms
from torchvision import models

device = torch.accelerator.current_accelerator().type if torch.accelerator.is_available() else "cpu"
print(f"Using {device} device")

def ImagePreprocessor(image_path, target_size=112):
    try:
        img = Image.open(image_path).convert('RGB')
    except Exception as e:
        print("Error loading image: ",e)
        return None
    
    padded_img = ImageOps.pad(img, size=(target_size,target_size), color=(0,0,0))

    preprocesses = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]) 
    ])

    img_tensor = preprocesses(padded_img)
    final_tesnor = img_tensor.unsqueeze(0)

    return final_tesnor

class VisionEncoder(nn.Module):
    def __init__(self, embedding_dim=256,freeze_weights=True):
        super().__init__()

        self.backbone = models.mobilenet_v3_small(weights='DEFAULT')
        self.backbone.classifier = nn.Identity()
        self.projection = nn.Linear(576, embedding_dim)

        if freeze_weights:
            for param in self.backbone.parameters():
                param.requires_grad = False

    def forward(self,x):
        x = self.backbone(x)
        x = self.projection(x)

        return x
    
if __name__ == "__main__":
    print("Initializing smart vision encoder...")
    model = VisionEncoder(embedding_dim=256)

    print("Preprocessing the images...")
    