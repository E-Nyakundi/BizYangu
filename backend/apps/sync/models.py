# apps.sync deliberately has no models of its own. It reads and writes
# existing models (Transaction, Product, ProductUnit, Customer,
# StockMovement, RepackageEvent, CustomerPayment) that other apps already
# own — see views.py's PULL_MODELS and services.py's push handlers. This
# file exists only so Django recognizes apps.sync as an app with a
# (trivially empty) models module.
