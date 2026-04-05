import torch
import torch.nn as nn
from PIL import Image, ImageOps
import torchvision.transforms as transforms

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
    def __init__(self, embedding_dim=256):
        super().__init__()

        self.conv1 = nn.Conv2d(in_channels=3,out_channels=16,kernel_size=3,padding=1)
        self.relu1 = nn.ReLU()
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.conv2 = nn.Conv2d(in_channels=16,out_channels=32,kernel_size=3,padding=1)
        self.relu2 = nn.ReLU()
        self.pool2 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.conv3 = nn.Conv2d(in_channels=32,out_channels=64,kernel_size=3,padding=1)
        self.relu3 = nn.ReLU()
        self.pool3 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.conv4 = nn.Conv2d(in_channels=64,out_channels=128,kernel_size=3,padding=1)
        self.relu4 = nn.ReLU()
        self.pool4 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.flatten = nn.Flatten()
        self.projection = nn.Linear(128*7*7,embedding_dim)

    def forward(self,x):
        x = self.pool1(self.relu1(self.conv1(x)))
        x = self.pool2(self.relu2(self.conv2(x)))
        x = self.pool3(self.relu3(self.conv3(x)))
        x = self.pool4(self.relu4(self.conv4(x)))

        x = self.flatten(x)
        x = self.projection(x)

        return x
    
if __name__ == "__main__":
    print("Starting vision encoding...")
    model = VisionEncoder(embedding_dim=256)

    print("Preprocessing Image...")
    img_path = "Gaia/python/test_imgs/1.png"
    img_tensor = ImagePreprocessor(img_path,target_size=112)

    print("Passing image through neural net...")
    model = VisionEncoder(embedding_dim=256)
    output = model(img_tensor)

    print(f"Output shape: {output.shape}")
    print(f"Output: {output}") 