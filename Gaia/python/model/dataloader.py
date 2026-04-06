import os 
import pandas as pd 
from torch.utils.data import DataLoader, Dataset
from .vision import ImagePreprocessor

class GeneralImageDataset(Dataset):
    def __init__(self,csv_path,img_dir,tokenizer=None):
        self.data = pd.read_csv(csv_path)
        self.img_dir = img_dir
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, index):
        img_name = os.path.join(self.img_dir,self.data.iloc[index,0])
        caption = self.data.iloc[index,1]

        image_tensor = ImagePreprocessor(img_name, target_size=112)
        if image_tensor is None:
            image_tensor = image_tensor.squeeze(0)

        return image_tensor,caption 