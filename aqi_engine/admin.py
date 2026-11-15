from django.contrib import admin
from .models import (
    User,
    Aqi3nf,
    EvaluationAlgorithm,
    SparkJobLog,
    VerifierValidationQueue,
)

admin.site.register(User)
admin.site.register(Aqi3nf)
admin.site.register(EvaluationAlgorithm)
admin.site.register(SparkJobLog)
admin.site.register(VerifierValidationQueue)
