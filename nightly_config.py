# -*- coding: utf-8 -*-
"""
Created on Thu Aug  2 12:02:05 2018

@author: V0010894
"""

import pandas as pd
import numpy as np
from datetime import datetime
import boto3

from get_atspm_detectors import get_atspm_detectors

BUCKET = 'agency-spm' #TODO: Update

# get Good/Authoritative Detector Config (det_config) and write to feather
def get_det_config(adc, date_string):
    # -- ---------------------------------
    # -- Included detectors --
    #  SignalID/Detector pairs with vol > 0 over the past year
    #  over a sample of dates between 8am-9am
    incld = (pd.read_csv('included_detectors.csv')
                .sort_values(['SignalID','Detector'])
                .set_index(['SignalID','Detector']))
    
    # -- -------------------------------------------------- --
    # -- ATSPM Detector Config (from reduce function above) --
    
    adc = ad[['SignalID',
             'Detector',
             'ProtectedPhaseNumber',
             'PermissivePhaseNumber',
             'TimeFromStopBar',
             'IPAddress']]
    adc = adc.rename(columns={'ProtectedPhaseNumber': 'ProtPhase',
                            'PermissivePhaseNumber': 'PermPhase'})
    adc['CallPhase'] = np.where(adc.ProtPhase > 0, adc.ProtPhase, adc.PermPhase)
    
    try:
        adc = adc[adc.SignalID != 'null']
    except:
        pass
    adc = adc[~adc.Detector.isna()]
    adc = adc[~adc.CallPhase.isna()]
    
    adc.SignalID = adc.SignalID.astype('int')
    adc.Detector = adc.Detector.astype('int')
    adc.CallPhase = adc.CallPhase.astype('int')
    
    adc = adc.set_index(['SignalID','Detector'])
    
    det_config = adc.join(incld).rename(columns={'Unnamed: 0': 'in_cel'}).sort_index()
    
    det_config.TimeFromStopBar = det_config.TimeFromStopBar.fillna(0).round(1)
    
    det_config = det_config.reset_index()[['SignalID',
                                       'Detector',
                                       'CallPhase',
                                       'TimeFromStopBar',
                                       'in_cel']]
    return det_config

s3 = boto3.client('s3')

date_string = datetime.today().strftime('%Y-%m-%d')




ad = get_atspm_detectors()
ad_csv_filename = 'ATSPM_Det_Config_{}.csv'.format(date_string)
ad.to_csv(ad_csv_filename)

# upload to s3
key = 'atspm_det_config/date={}/ATSPM_Det_Config.csv'.format(date_string)
s3.upload_file(Filename=ad_csv_filename, 
               Bucket=BUCKET, 
               Key=key)






det_config = get_det_config(ad, date_string)
dc_filename = 'ATSPM_Det_Config_Good_{}.feather'.format(date_string)
det_config.to_feather(dc_filename)

# upload to s3
key = 'atspm_det_config_good/date={}/ATSPM_Det_Config_Good.feather'.format(date_string)
s3.upload_file(Filename=dc_filename, 
               Bucket=BUCKET, 
               Key=key)

