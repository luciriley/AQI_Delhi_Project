from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when

def run_multi_algorithm_evaluation():
    spark = SparkSession.builder \
        .appName("AQI-MultiAlgo-Processor") \
        .config("spark.jars", "/path/to/mysql-connector-j.jar") \
        .getOrCreate()

    jdbc_url = "jdbc:mysql://127.0.0.1:3306/aqi_project"
    db_properties = {"user": "root", "password": "log3=0.47712125471966", "driver": "com.mysql.cj.jdbc.Driver"}

    # Fetch spatial array view matrix
    df = spark.read.jdbc(url=jdbc_url, table="v_pyspark_training_matrix", properties=db_properties)

    # Indian NAQI calculation scale vector map
    df_algo_a = df.withColumn("algo_a_score", col("pm2_5") * 1.1)

    # US-EPA Breakpoint evaluation step logic
    df_final = df_algo_a.withColumn(
        "algo_b_score",
        when(col("pm2_5") <= 30, col("pm2_5") * 1.5).otherwise(col("pm2_5") * 2.2)
    )

    df_final.select("id", "benchmark_aqi", "algo_a_score", "algo_b_score").show(10)
    spark.stop()

