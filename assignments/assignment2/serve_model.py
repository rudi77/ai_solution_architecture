from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import numpy as np
import pandas as pd
import uvicorn

# --------------------------
# Load trained model pipeline
# --------------------------

model = joblib.load("model/RandomForest_pipeline.pkl")  # or LinearRegression_pipeline.pkl

# Define expected feature order
FEATURE_NAMES = [
    "MedInc", "HouseAge", "AveRooms", "AveBedrms",
    "Population", "AveOccup", "Latitude", "Longitude"
]

# --------------------------
# Define input schema using Pydantic
# --------------------------

class HousingFeatures(BaseModel):
    MedInc: float
    HouseAge: float
    AveRooms: float
    AveBedrms: float
    Population: float
    AveOccup: float
    Latitude: float
    Longitude: float

# --------------------------
# Initialize FastAPI app
# --------------------------

app = FastAPI(
    title="California Housing Model API",
    description="Mock deployment for predicting median house prices using a trained ML pipeline.",
    version="1.0"
)

@app.get("/")
def root():
    return {"message": "California Housing Prediction API is running."}

@app.post("/predict")
def predict_price(features: HousingFeatures):
    # Convert input data to pandas DataFrame with correct column names
    input_data = {name: getattr(features, name) for name in FEATURE_NAMES}
    input_df = pd.DataFrame([input_data])
    
    # Make prediction
    prediction = model.predict(input_df)

    return {
        "predicted_median_house_value": float(prediction[0])
    }

# --------------------------
# Local launch (for testing)
# --------------------------

if __name__ == "__main__":
    uvicorn.run("serve_model:app", host="0.0.0.0", port=8082, reload=True)
