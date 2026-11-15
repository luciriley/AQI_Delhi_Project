import os
import json
from datetime import datetime
import pymysql
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import RandomForestRegressor, GBTRegressor, LinearRegression
from pyspark.ml.evaluation import RegressionEvaluator

DB_CONFIG = {
    'host': '127.0.0.1',
    'database': 'aqi_project',
    'user': 'root',
    'password': 'log3=0.47712125471966',
}


def run_pyspark_job(job_id: int, algorithm_id: int, formula_spec: str):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, location_id,
                   CAST(temp_c AS DOUBLE),
                   CAST(humidity AS DOUBLE),
                   CAST(pressure_mb AS DOUBLE),
                   CAST(windspeed_kph AS DOUBLE),
                   CAST(benchmark_aqi AS DOUBLE)
            FROM v_pyspark_training_matrix
            WHERE temp_c IS NOT NULL
              AND humidity IS NOT NULL
              AND pressure_mb IS NOT NULL
              AND windspeed_kph IS NOT NULL
              AND benchmark_aqi IS NOT NULL
        """)
        rows = cursor.fetchall()
        record_count = len(rows)

        spark = (
            SparkSession.builder
            .master("local[*]")
            .appName(f"AQI_Forecast_Job_{job_id}")
            .config("spark.ui.enabled", "false")
            .getOrCreate()
        )

        columns = ["id", "location_id", "temp_c", "humidity", "pressure_mb", "windspeed_kph", "label"]
        df = spark.createDataFrame(rows, schema=columns)

        feature_cols = ["location_id", "temp_c", "humidity", "pressure_mb", "windspeed_kph"]
        assembler = VectorAssembler(inputCols=feature_cols, outputCol="features")
        ml_df = assembler.transform(df).select("id", "location_id", "features", "label")

        train_df, test_df = ml_df.randomSplit([0.8, 0.2], seed=42)

        spec_lower = (formula_spec or "").lower()
        if "gbt" in spec_lower:
            regressor = GBTRegressor(featuresCol="features", labelCol="label", maxDepth=6, maxIter=40)
        elif "linear" in spec_lower:
            regressor = LinearRegression(featuresCol="features", labelCol="label")
        else:
            regressor = RandomForestRegressor(featuresCol="features", labelCol="label", numTrees=80, maxDepth=10)

        model = regressor.fit(train_df)
        predictions = model.transform(test_df)

        rmse = RegressionEvaluator(metricName="rmse").evaluate(predictions)
        mae = RegressionEvaluator(metricName="mae").evaluate(predictions)

        # Predict latest weather row per location_id for the Public Dashboard
        cursor.execute("""
            SELECT t.location_id,
                   CAST(t.temp_c AS DOUBLE),
                   CAST(t.humidity AS DOUBLE),
                   CAST(t.pressure_mb AS DOUBLE),
                   CAST(t.windspeed_kph AS DOUBLE)
            FROM aqi_3nf t
            INNER JOIN (
                SELECT location_id, MAX(id) AS max_id
                FROM aqi_3nf
                GROUP BY location_id
            ) m ON t.id = m.max_id
        """)
        latest_loc_rows = cursor.fetchall()
        latest_df = spark.createDataFrame(
            latest_loc_rows,
            schema=["location_id", "temp_c", "humidity", "pressure_mb", "windspeed_kph"]
        )
        latest_preds = model.transform(assembler.transform(latest_df)).select("location_id", "prediction").collect()
        station_predictions = {str(int(r["location_id"])): int(round(float(r["prediction"]))) for r in latest_preds}

        os.makedirs("spark_outputs", exist_ok=True)
        sample_rows = (
            predictions.select("id", "location_id", "label", "prediction")
            .orderBy(col("id").desc())
            .limit(60)
            .collect()
        )
        output_payload = {
            "job_id": job_id,
            "algorithm_id": algorithm_id,
            "rmse": round(float(rmse), 2),
            "mae": round(float(mae), 2),
            "station_predictions": station_predictions,
            "samples": [
                {
                    "id": int(r["id"]),
                    "location_id": int(r["location_id"]),
                    "actual": float(r["label"]),
                    "predicted": round(float(r["prediction"]), 2),
                }
                for r in reversed(sample_rows)
            ],
        }
        with open(f"spark_outputs/algo_{algorithm_id}_latest.json", "w") as f:
            json.dump(output_payload, f)

        cursor.execute(
            """
            UPDATE spark_job_logs
            SET status = 'completed',
                execution_end = %s,
                records_processed = %s
            WHERE job_id = %s
            """,
            (datetime.now(), record_count, job_id),
        )
        conn.commit()
        spark.stop()

    except Exception as exc:
        cursor.execute(
            """
            UPDATE spark_job_logs
            SET status = 'failed',
                execution_end = %s,
                error_message = %s
            WHERE job_id = %s
            """,
            (datetime.now(), str(exc)[:1000], job_id),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()
