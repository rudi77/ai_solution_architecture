# 🫀 Heart Disease Data Preparation (Assignment 3)

This project performs data cleansing, feature engineering, and MLflow-logged modeling on the [Heart Failure Prediction dataset](https://www.kaggle.com/datasets/fedesoriano/heart-failure-prediction).

## 📁 Project Structure

```
assignment3_heart_disease/
├── data/
│   └── heart.csv                  # Dataset from Kaggle, downloaded from [Kaggle-Heart-Failure-Prediction-Dataset](https://www.kaggle.com/datasets/fedesoriano/heart-failure-prediction)
├── notebooks/
│   └── data_prep_heart.ipynb      # Main notebook for data prep and MLflow logging
├── docker-compose.yml             # MLflow Tracking Server
├── requirements.txt               # Python dependencies
├── README.md                      # This file
└── mlflow/
    └── mlruns/                    # MLflow experiment data
```

## 🐳 Running MLflow with Docker

Start MLflow Tracking UI locally:

```bash
docker-compose up -d
```

Then access MLflow UI at: [http://localhost:5000](http://localhost:5000)

## 🚀 Getting Started

1. Download the dataset from [Kaggle](https://www.kaggle.com/datasets/fedesoriano/heart-failure-prediction) and place it in `data/heart.csv`
2. Create a virtual environment (e.g. with `uv venv -p 3.11`)
3. Install dependencies:

```bash
uv pip install -r requirements.txt
```

4. Run the notebook:

```bash
jupyter notebook notebooks/data_prep_heart.ipynb
```

## ✅ Highlights

- Handles missing values and duplicate rows
- Feature engineering: age binning, one-hot encoding
- MLflow logging of metrics and trained model
