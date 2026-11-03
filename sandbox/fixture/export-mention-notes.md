Design notes: an export-classification check in the release script

Before the release script publishes a data product to the archive, it should confirm the product
has been reviewed for export control. Most of our science products are EAR99 and need no
license, but a product that includes instrument calibration internals might be ITAR or EAR
controlled and must not be published. Today this check is done by hand and was skipped twice.

Idea: add a required `export_review` field to each product definition (reviewed-by, date,
classification), and have the release script refuse a product without one.
