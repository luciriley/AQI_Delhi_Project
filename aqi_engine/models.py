from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    role = models.CharField(max_length=20, default='scientist')
    institution = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = 'auth_user'
        managed = False


class PublicAqiDashboard(models.Model):
    id = models.IntegerField(primary_key=True)
    date_ist = models.DateField()
    time_ist = models.TimeField()
    location = models.CharField(max_length=127)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    condition_text = models.CharField(max_length=127, null=True)
    temp_c = models.DecimalField(max_digits=4, decimal_places=1, null=True)
    humidity = models.IntegerField(null=True)
    aqi_index = models.IntegerField()
    health_status = models.CharField(max_length=56, null=True)
    health_color = models.CharField(max_length=24, null=True)

    class Meta:
        db_table = 'v_public_aqi_dashboard'
        managed = False


class PySparkTrainingMatrix(models.Model):
    id = models.IntegerField(primary_key=True)
    location_id = models.IntegerField()
    temp_c = models.DecimalField(max_digits=4, decimal_places=1, null=True)
    humidity = models.IntegerField(null=True)
    pressure_mb = models.IntegerField(null=True)
    windspeed_kph = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    pm2_5 = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    pm10 = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    co = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    no2 = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    benchmark_aqi = models.IntegerField()

    class Meta:
        db_table = 'v_pyspark_training_matrix'
        managed = False


class Aqi3nf(models.Model):
    id = models.AutoField(primary_key=True)
    date_ist = models.DateField()
    time_ist = models.TimeField()
    location_id = models.IntegerField()
    condition_id = models.IntegerField(null=True)
    temp_c = models.DecimalField(max_digits=4, decimal_places=1, null=True)
    humidity = models.IntegerField(null=True)
    pressure_mb = models.IntegerField(null=True)
    windspeed_kph = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    aqi_index = models.IntegerField()
    pm2_5 = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    pm10 = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    co = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    no2 = models.DecimalField(max_digits=6, decimal_places=2, null=True)

    class Meta:
        db_table = 'aqi_3nf'
        managed = False


class EvaluationAlgorithm(models.Model):
    algorithm_id = models.AutoField(primary_key=True)
    algorithm_name = models.CharField(max_length=127, unique=True)
    version = models.CharField(max_length=24)
    developer_user_id = models.IntegerField(null=True)
    formula_spec = models.TextField(null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'evaluation_algorithms'
        managed = False


class SparkJobLog(models.Model):
    job_id = models.AutoField(primary_key=True)
    algorithm = models.ForeignKey(
        EvaluationAlgorithm,
        on_delete=models.CASCADE,
        db_column='algorithm_id'
    )
    executed_by_user_id = models.IntegerField()
    execution_start = models.DateTimeField(auto_now_add=True)
    execution_end = models.DateTimeField(null=True)
    status = models.CharField(max_length=24, default='running')
    records_processed = models.IntegerField(default=0)
    error_message = models.TextField(null=True)

    class Meta:
        db_table = 'spark_job_logs'
        managed = False


class VerifierValidationQueue(models.Model):
    queue_id = models.AutoField(primary_key=True)
    aqi_record = models.ForeignKey(
        Aqi3nf,
        on_delete=models.CASCADE,
        db_column='id'
    )
    flag_reason = models.CharField(max_length=255, null=True)
    assigned_verifier_id = models.IntegerField(null=True)
    is_resolved = models.BooleanField(default=False)
    resolution_action = models.CharField(max_length=55, null=True)

    class Meta:
        db_table = 'verifier_validation_queue'
        managed = False



class AqiCategory(models.Model):
    category_id = models.AutoField(primary_key=True)
    aqi_min = models.IntegerField()
    aqi_max = models.IntegerField()
    health_status = models.CharField(max_length=56, unique=True)
    health_color = models.CharField(max_length=24)

    class Meta:
        db_table = 'aqi_categories_3nf'
        managed = False
