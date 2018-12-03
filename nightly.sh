#!/bin/bash -l

cd $HOME/Code/AGENCY/Flexdashboard-Report
Rscript Monthly_Report_Calcs.R
Rscript Monthly_Report_Package.R
