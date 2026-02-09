
import io
import requests
import urllib3
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# New imports for Image Processing
from PIL import Image
from pyzbar.pyzbar import decode

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI()

# Allow your HTML file to communicate with this Python server
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_methods=["*"], 
    allow_headers=["*"]
)

def perform_deep_audit(barcode: str):
    clean_barcode = str(barcode).strip()
    
    mirrors = [
        {"url": "https://world.openfoodfacts.org", "label": "FOOD REGISTRY (GLOBAL)"},
        {"url": "https://in.openfoodfacts.org", "label": "FOOD REGISTRY (INDIA)"},
        {"url": "https://world.openproductfacts.org", "label": "HOUSEHOLD REGISTRY"},
        {"url": "https://world.openbeautyfacts.org", "label": "BEAUTY & PERSONAL CARE"}
    ]
    
    headers = {'User-Agent': 'AgriSmartAudit/1.0'}

    for mirror in mirrors:
        target_url = f"{mirror['url']}/api/v0/product/{clean_barcode}.json"
        try:
            resp = requests.get(target_url, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == 1:
                    p = data.get("product", {})
                    nova = p.get('nova_group', 0)
                    additives = p.get('additives_tags', [])
                    
                    return {
                        "found": True,
                        "category": mirror['label'],
                        "barcode": clean_barcode,
                        "name": p.get('product_name') or p.get('product_name_en') or "Unknown Item",
                        "brand": p.get('brands') or "Generic Brand",
                        "origin": p.get('countries', 'Global Distribution'),
                        "ingredients": p.get('ingredients_text') or "Ingredients not listed in registry.",
                        "health": {
                            "safety_status": "GOOD" if (not nova or int(nova) < 4) and len(additives) < 5 else "HARMFUL",
                            "processing_lvl": f"Level {nova}" if nova else "N/A",
                            "chemical_count": len(additives),
                            "chemical_list": [a.replace('en:', '').upper() for a in additives]
                        }
                    }
        except Exception as e:
            continue
    return {"found": False}

@app.post("/scan")
async def scan(file: Optional[UploadFile] = File(None), manual_barcode: Optional[str] = Form(None)):
    results = []
    
    # Priority 1: Manual Input
    if manual_barcode and manual_barcode.strip() != "":
        results.append({"details": perform_deep_audit(manual_barcode)})
    
    # Priority 2: Optical Extraction (Image)
    elif file:
        try:
            contents = await file.read()
            img = Image.open(io.BytesIO(contents))
            detected_barcodes = decode(img)
            
            if detected_barcodes:
                barcode_data = detected_barcodes[0].data.decode("utf-8")
                results.append({"details": perform_deep_audit(barcode_data)})
            else:
                return {"success": False, "message": "No barcode found in image."}
        except Exception as e:
            return {"success": False, "message": f"Optical error: {str(e)}"}
    
    else:
        return {"success": False, "message": "No input provided."}

    return {"success": True, "data": results}

# if __name__ == "__main__":
#     uvicorn.run(app, host="127.0.0.1", port=8000)
app=app