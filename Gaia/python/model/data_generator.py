import os 
import requests 
from bs4 import BeautifulSoup
import fitz
from PIL import Image
import io
import urllib.parse

def scrape_and_extract(url,output_dir="charts"):
    os.makedirs(output_dir,exist_ok=True)
    print(f"Scraping {url} for PDFs...")

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    try:
        response = requests.get(url,headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Could not load the webpage: {e}")
        return
    
    pdf_links = []
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and href.lower().endswith('.pdf'):
            if not href.startswith('http'):
                href = urllib.parse.urljoin(url, href)
            pdf_links.append(href)

    print(f"Found {len(pdf_links)} PDF links. Starting extraction...")

    img_count = 0
    for i,pdf_url in enumerate(pdf_links):
        try:
            print(f"Downloading PDF {i+1} from {pdf_url}...")
            pdf_response = requests.get(pdf_url,headers=headers)

            doc = fitz.open(stream=pdf_response.content, filetype="pdf")

            print(f"Scanning {len(doc)} pages for charts...")
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)

                for img_idx, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]

                    image = Image.open(io.BytesIO(image_bytes))
                    if image.width>250 and image.height>250:
                        img_path = os.path.join(output_dir, f"doc_{i}_page_{page_num}_img_{img_count}.png")
                        image.save(img_path)
                        img_count += 1

        except Exception as e:
            print(f"Failed to process {pdf_url}: {e}")

    print(f"Image extraction completed. Extraced {img_count} charts to your folder.")
    
url = "https://rbi.org.in/Scripts/AnnualReportPublications.aspx"
scrape_and_extract(url,output_dir="charts")