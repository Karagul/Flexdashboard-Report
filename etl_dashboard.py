# -*- coding: utf-8 -*-
"""
Created on Mon Nov 27 16:27:29 2017

@author: Alan.Toppen
"""
from datetime import datetime, timedelta
from multiprocessing.dummy import Pool
import pandas as pd
import sqlalchemy as sq
import pyodbc
import time
import os
import itertools
from spm_events import etl_main
import boto3
import yaml
from glob import glob

with open('Monthly_Report_AWS.yaml') as yaml_file:
    cred = yaml.load(yaml_file)

s3 = boto3.client('s3',
                  aws_access_key_id=cred['AWS_ACCESS_KEY_ID'],
                  aws_secret_access_key=cred['AWS_SECRET_ACCESS_KEY'])
ath = boto3.client('athena',
                  aws_access_key_id=cred['AWS_ACCESS_KEY_ID'],
                  aws_secret_access_key=cred['AWS_SECRET_ACCESS_KEY'])
ATHENADB = 'agency_spm' #TODO: Update
BUCKET = 'agency-spm' #TODO: Update
ATHENA_BUCKET = 'agency-spm-athena' #TODO: Update

'''
    df:
        SignalID [int64]
        TimeStamp [datetime]
        EventCode [str or int64]
        EventParam [str or int64]
    
    det_config:
        SignalID [int64]
        IP [str]
        PrimaryName [str]
        SecondaryName [str]
        Detector [int64]
        Call Phase [int64]
'''

def etl2(s, date_):
    
    dc_fn = 'ATSPM_Det_Config_Good_{}.feather'.format(date_.strftime('%Y-%m-%d'))
    if not os.path.exists(dc_fn):
        dc_fn = 'ATSPM_Det_Config_Good.feather'
    det_config = (pd.read_feather(dc_fn)
                    .assign(SignalID = lambda x: x.SignalID.astype('int64'))
                    .assign(Detector = lambda x: x.Detector.astype('int64'))
                    .rename(columns={'CallPhase':'Call Phase'}))
    
    left = det_config[det_config.SignalID==s]
    right = bad_detectors[(bad_detectors.SignalID==s) & (bad_detectors.Date==date_)]
    right = (right.assign(SignalID = lambda x: x.SignalID.astype('int64'))
                  .assign(Detector = lambda x: x.Detector.astype('int64')))

    det_config_good = (pd.merge(left, right, how = 'outer', indicator = True)
                         .loc[lambda x: x._merge=='left_only']
                         .drop(['Date','_merge'], axis=1))
    
    #sum(~pd.isnull(det_config_good['CallPhase.atspm']))
    
    query = """SELECT * FROM Controller_Event_Log 
               WHERE SignalID = '{}'
               AND EventCode in (1,4,5,6,8,9,31,81,82) 
               AND (Timestamp BETWEEN '{}' AND '{}');
               """
    start_date = date_
    end_date = date_ + pd.DateOffset(days=1) - pd.DateOffset(seconds=0.1)
    
    
    t0 = time.time()
    date_str = date_.strftime('%Y-%m-%d') #str(date_)[:10]
    print('{} | {} Starting...'.format(s, date_str))

    try:
        print('|{} reading from database...'.format(s))
        with engine.connect() as conn:
            df = pd.read_sql(sql=query.format(s, str(start_date)[:-3], str(end_date)[:-3]), con=conn)
            df = (df.rename(columns={'Timestamp':'TimeStamp'})
                    .assign(SignalID = df.SignalID.astype('int')))
        
        if len(df)==0:
            print('|{} no event data for this signal on {}.'.format(s, date_str))

        else:
    
            print('|{} creating cycles and detection events...'.format(s))
            c, d = etl_main(df, det_config_good)
            
            print('writing to files...')
            
            if not os.path.exists('../CycleData/' + date_str):
                os.mkdir('../CycleData/' + date_str)
            if not os.path.exists('../DetectionEvents/' + date_str):
                os.mkdir('../DetectionEvents/' + date_str)
                
            
            cd_file = '../CycleData/{}/cd_{}_{}.parquet'.format(date_str, s, date_str)
            de_file = '../DetectionEvents/{}/de_{}_{}.parquet'.format(date_str, s, date_str)
            
            c.to_parquet(cd_file) 
            d.to_parquet(de_file) 
            
            s3.upload_file(Filename=cd_file, 
                           Bucket=BUCKET, 
                           Key='cycles/date={}/cd_{}_{}.parquet'.format(date_str, s, date_str))
            s3.upload_file(Filename=de_file, 
                           Bucket=BUCKET, 
                           Key='detections/date={}/de_{}_{}.parquet'.format(date_str, s, date_str))
            
            os.remove(cd_file)
            os.remove(de_file)
            
    
            print('{}: {} seconds'.format(s, int(time.time()-t0)))
        
    
    except Exception as e:
        print(s, e)


        
        
    
if __name__=='__main__':

    t0 = time.time()
    
    if os.name=='nt':
        
        uid = os.environ['ATSPM_USERNAME']
        pwd = os.environ['ATSPM_PASSWORD']
        dsn = 'atspm_dsn'
        
        engine = sq.create_engine('mssql+pyodbc://{}:{}@{}'.format(uid, pwd, dsn),
                                  pool_size=20)
    
    elif os.name=='posix':

        def connect():
            return pyodbc.connect(
                'Driver=FreeTDS;' + 
                'SERVER={};'.format(os.environ['ATSPM_SERVER_INSTANCE']) +
                'DATABASE={};'.format(os.environ['ATSPM_DB']) +
                'PORT=1433;' +
                'UID={};'.format(os.environ['ATSPM_USERNAME']) +
                'PWD={};'.format(os.environ['ATSPM_PASSWORD']) +
                'TDS_Version=8.0;')
        
        engine = sq.create_engine('mssql://', creator=connect)
        
    
    bad_detectors = pd.read_feather('bad_detectors.feather')
    
    with open('Monthly_Report_calcs.yaml') as yaml_file:
        conf = yaml.load(yaml_file)

    start_date = conf['start_date']
    if start_date == 'yesterday': 
        start_date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    end_date = conf['end_date']
    if end_date == 'yesterday': 
        end_date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Placeholder for manual override of start/end dates
    #start_date = '2018-10-01'
    #end_date = '2018-10-04'
    
    dates = pd.date_range(start_date, end_date, freq='1D')
                                        
    corridors_filename = conf['corridors_filename']
    corridors = pd.read_feather(corridors_filename)
    corridors = corridors[~corridors.SignalID.isna()]
    
    signalids = list(corridors.SignalID.astype('int').values)
    
    for date_ in dates:

        pool = Pool(18) #24
        asyncres = pool.starmap(etl2, list(itertools.product(signalids, [date_])))
        pool.close()
        pool.join()
    

    
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
        
        response = ath.start_query_execution(QueryString='MSCK REPAIR TABLE cycledata', 
                                             QueryExecutionContext={'Database': ATHENADB},
                                             ResultConfiguration={'OutputLocation': 's3://{}'.format(ATHENA_BUCKET)})
        response = ath.start_query_execution(QueryString='MSCK REPAIR TABLE detectionevents', 
                                             QueryExecutionContext={'Database': ATHENADB},
                                             ResultConfiguration={'OutputLocation': 's3://{}'.format(ATHENA_BUCKET)})
        
    print('\n{} signals in {} days. Done in {} minutes'.format(len(signalids), len([date_]), int((time.time()-t0)/60)))

