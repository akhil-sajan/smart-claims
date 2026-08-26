# Sample data

Sample datasets for this project (policies/claims/customers CSVs, claim photos,
training images, telematics parquet files) are sourced from the public dataset
in [datamyselfai/databricks-zero-to-hero-course](https://github.com/datamyselfai/databricks-zero-to-hero-course).

They're gitignored here (117MB, not meant for repo history). To get them locally:

```bash
git clone https://github.com/datamyselfai/databricks-zero-to-hero-course.git
cp -r databricks-zero-to-hero-course/data ./data
```

## Layout

- `sql_server/` — customers.csv, policies.csv, claims.csv (loaded into SQL Server for CDC)
- `claims/images/` — claim photos, filenames indicate severity (e.g. `4_High.jpg`)
- `claims/metadata/image_metadata.csv` — maps images to claim_no / chassis_no
- `training_imgs/` — labeled accident images (ok / minor / major) for the damage classifier
- `telematics/` — parquet files of simulated driving telemetry, replayed into Kinesis
