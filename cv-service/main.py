from fastapi import FastAPI, File, UploadFile
from ultralytics import YOLO
import numpy as np
import cv2
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load YOLO model once
model = YOLO("yolov8n.pt")

@app.post("/detect")
async def detect_images(files: list[UploadFile] = File(...)):

    results_output = []

    for file in files:
        try:
            # Read image from request
            contents = await file.read()
            np_arr = np.frombuffer(contents, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if img is None:
                results_output.append({
                    "image": file.filename,
                    "error": "Invalid image"
                })
                continue

            # Run YOLO detection
            results = model(img)

            image_objects = []

            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    class_name = model.names[cls_id]
                    confidence = float(box.conf[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                    image_objects.append({
                        "object": class_name,
                        "confidence": round(confidence, 2),
                        "coordinates": [x1, y1, x2, y2]
                    })
            
            print(image_objects)

            results_output.append({
                "image": file.filename,
                "objects": image_objects
            })

        except Exception as e:
            results_output.append({
                "image": file.filename,
                "error": str(e)
            })

    return {"results": results_output}