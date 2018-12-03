Instructions to Implement ATSPM Dashboard
=========================================

## Requirements to set up the Environment

There are several different steps needed to create the dashboard and it is somewhat complex, due to the environment and resources available when it was first created. In addition to the hardware and environment setup, it requires at least a basic knowledge of the Python and R programming languages, understanding of database connections, and the ability to do basic troubleshooting as every IT environment is a bit different. On the last point, a VPN may be required, or proxy authentication, for instance. In the future it is possible the installation of this system may require no understanding of the different programming languages, but that is not the case currently.

For questions, please feel free to contact the developer at [alan.toppen@kimley-horn.com](mailto:alan.toppen@kimley-horn.com?subject=ATSPM%20Dashboard%20Installation%20Question) and I will assist as best I can.

It requires the following:

- An ATSPM deployment (e.g., [https://traffic.dot.ga.gov/ATSPM](https://traffic.dot.ga.gov/ATSPM)), which consists of a server, database and programs to acquire high-resolution traffic data from signal controllers (see [https://www.fhwa.dot.gov/innovation/everydaycounts/edc_4/atspm.cfm](https://www.fhwa.dot.gov/innovation/everydaycounts/edc_4/atspm.cfm))

- An analysis workstation or server with:
    - Access to the ATSPM database
    - A few GB of local storage
    - [Anaconda for Python 3](https://www.anaconda.com/) with requisite packages installed
    - [R](https://www.r-project.org/) and [RStudio](https://www.rstudio.com/) with requisite libraries installed

- An Amazon Web Services (AWS) account.

- A shinyapps.io account (http://www.shinyapps.io/)

## Installation Steps

- Set up AWS S3
    - Create AGENCY-spm bucket and subfolder structure (e.g., GDOT-spm, VDOT-spm)
    
        /atspm_det_config
        
        /bad_detectors
        
        /cycles
        
        /detections
        
        /signal_dashboards

- Set up AWS Athena
    - Create AGENCY_spm Athena database (e.g., gdot_spm, vdot_spm)
    - [Download Athena JDBC Driver](https://docs.aws.amazon.com/athena/latest/ug/connect-with-jdbc.html)
    - Create CycleData, DetectionEvents tables

    
```HiveQL
CREATE EXTERNAL TABLE `cycledata`(
  `signalid` int, 
  `phase` int, 
  `cyclestart` timestamp, 
  `phasestart` timestamp, 
  `phaseend` timestamp, 
  `eventcode` int, 
  `termtype` int, 
  `duration` double, 
  `volume` int)
PARTITIONED BY ( 
  `date` string)
ROW FORMAT SERDE 
  'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe' 
STORED AS INPUTFORMAT 
  'org.apache.hadoop.mapred.TextInputFormat' 
OUTPUTFORMAT 
  'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION
  's3://AGENCY-spm/cycles' # e.g., GDOT-spm/cycles, VDOT-spm/cycles
```

```HiveQL
CREATE EXTERNAL TABLE `detectionevents`(
  `signalid` int, 
  `phase` int, 
  `cyclestart` timestamp, 
  `phasestart` timestamp, 
  `eventcode` int, 
  `dettimestamp` timestamp, 
  `detduration` double, 
  `dettimeincycle` double, 
  `dettimeinphase` double)
PARTITIONED BY ( 
  `date` string)
ROW FORMAT SERDE 
  'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe' 
STORED AS INPUTFORMAT 
  'org.apache.hadoop.mapred.TextInputFormat' 
OUTPUTFORMAT 
  'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION
  's3://AGENCY-spm/detections' # e.g., GDOT-spm/detections, VDOT-spm/detections
```


- Set up AWS IAM permissions  
    - Create IAM Group: AGENCY (e.g., GDOT, VDOT)
    - Attach the following policies
        - AmazonS3FullAccess
        - AmazonAthenaFullAccess
        - IAMUserChangePassword
    - Create a policy called JDBC with the text below
    - Create user AGENCY (e.g., GDOT, VDOT)
        - Assign to group
        - Create credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION)
```JSON
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "athena:GetQueryResultsStream",
                "athena:*"
            ],
            "Resource": "*"
        }
    ]
}
```


- Set up environment variables on the analysis workstation or server:
```
    ATSPM_SERVER_INSTANCE
    ATSPM_DB             
    ATSPM_USERNAME       
    ATSPM_PASSWORD       
    AWS_ACCESS_KEY_ID    
    AWS_SECRET_ACCESS_KEY
    AWS_DEFAULT_REGION   
```

- Clone this Github repository to a folder on the analysis workstation or server
- Modify Monthly_Report_AWS.yaml
- Modify Monthly_Report_calcs.yaml
- Modify Monthly_Report.yaml
- Populate corridors file

## Run Calculations

Unlike the ATSPM site, which runs all calculations from the raw data in the database for every chart requested by the user, this dashboard runs calculations daily and stores the aggregated data tables that are then read by the dashboard code to present the monthly metrics and plots. Therefore, the analysis workstation or server should schedule the calculation scripts to run each day.

Depending on the workstation on which the calculations are run, the nightly calculations may take ~20 minutes for a few dozen intersections to ~4 hours for a few thousand intersections.

Because the ATSPM database does not track configuration changes over time (e.g., new detectors added, detector phase assignments changed, etc.), this system has a script that records the current intersection detector configuration each day. This daily configuration is then used for the subsequent calculations.

The following scripts should be scheduled to run each day:
```Shell
python nightly_config.py
Rscript Monthly_Report_Calcs.R
Rscript Monthly_Report_Package.R
```

## Publish the Dashboard Online

- Create account on shinyapps.io
- Open Monthly_Report.Rmd and select "Run Document"
- Publish dashboard to shinyapps.io
- In shinyapps.io, go to dashboard and open Monthly_Report application settings
    - Increase instance size
    - Adjust Instance idle timeout, if desired

