# NEOM Smart City Traffic Model
This project develops an advanced traffic analysis and forecasting model for a NEOM-inspired smart city, part of a data science portfolio targeting Saudi Arabia's Vision 2030 initiatives. Using synthetic traffic data, the project demonstrates senior-level expertise in data preprocessing, feature engineering, predictive modeling (ARIMA, LSTM, XGBoost), and multi-level visualizations, tailored to optimize urban mobility in futuristic cities like NEOM.
Project Overview
The model simulates traffic patterns across five city zones, incorporating features like vehicle counts, speeds, congestion, weather, events, and rush hours. It employs:

Exploratory Data Analysis (EDA): To uncover trends and correlations.
Predictive Modeling:
ARIMA for time-series forecasting of vehicle counts.
LSTM neural networks for multivariate traffic predictions.
XGBoost for congestion score regression.


Visualizations: Static plots, interactive dashboards, and geospatial heatmaps for stakeholder insights.

This project showcases skills in handling IoT-driven urban data, advanced machine learning, and professional-grade visualization, aligning with NEOM’s smart city objectives.
Features

Synthetic Data Generation: Realistic traffic data with features like weather, events, road types, and rush hours.
Feature Engineering: Lagged variables, rolling averages, and categorical encodings for robust modeling.
Modeling:
ARIMA for baseline forecasting.
LSTM for capturing non-linear traffic patterns.
XGBoost for multivariate congestion prediction.


Visualizations:
Time-series plots of vehicle counts and speeds.
Boxplots for congestion by weather.
Interactive Plotly dashboards and geospatial scatter plots.
Model performance comparison (MAE, RMSE).


Portfolio Value: Demonstrates expertise in smart city analytics, relevant to Vision 2030 projects.

Prerequisites

Python 3.8+

Libraries:
pip install numpy pandas matplotlib seaborn plotly scikit-learn tensorflow xgboost statsmodels


Git (for cloning the repository)


Setup

Clone the Repository:
git clone https://github.com/MuhammadTalha121/smart-city-traffic-model.git
cd smart-city-traffic-model


Install Dependencies:
pip install -r requirements.txt

Alternatively, install the required libraries listed above.

Run the Script:
python neom_traffic_model_enhanced.py



Usage

Running the Script: Execute neom_traffic_model_enhanced.py to:
Generate synthetic traffic data (enhanced_traffic_data.csv).
Perform EDA and save visualizations (e.g., traffic_volume.png).
Train and evaluate ARIMA, LSTM, and XGBoost models.
Create interactive dashboards (traffic_dashboard.html).


Output Files:
Dataset: enhanced_traffic_data.csv
Visualizations:
traffic_volume.png: Vehicle counts by zone.
congestion_weather.png: Congestion by weather.
congestion_geospatial.html: Geospatial congestion map.
arima_forecast.png: ARIMA forecast.
lstm_forecast.png: LSTM predictions (featured in LinkedIn post).
xgboost_importance.png: XGBoost feature importance.
model_comparison.png: Model performance metrics.
traffic_dashboard.html: Interactive traffic dashboard.




Customizing: Modify parameters in generate_enhanced_traffic_data() (e.g., n_days, zones) to adjust the dataset size.

Outputs
The script generates:

A comprehensive dataset with enriched features (e.g., weather, rush hours).
Professional visualizations for technical and non-technical audiences.
Predictive models with evaluated performance (MAE, RMSE).
An interactive dashboard for dynamic traffic exploration.

Example visualization: LSTM forecast plot (lstm_forecast.png):
Acknowledgments

Inspired by NEOM and Saudi Arabia’s Vision 2030 smart city initiatives.
Built with Python libraries: NumPy, Pandas, Matplotlib, Seaborn, Plotly, Scikit-learn, TensorFlow, XGBoost, Statsmodels.
Synthetic data designed based on smart city frameworks.

License
This project is licensed under the MIT License. See the LICENSE file for details.

For questions or collaboration, connect with me on LinkedIn or open an issue on GitHub.
