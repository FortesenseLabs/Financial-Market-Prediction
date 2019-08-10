import matplotlib
matplotlib.use('Agg')
import requests
import os
import yaml
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.utils.data
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm
import matplotlib.pyplot as plt
import urllib3
import cryptocompare
from datetime import datetime
from models.architectures import TimeRNN
from utils.preprocessing import MinMaxScaler

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def get_config(file_loc='config.yaml'):
    return yaml.safe_load(open(file_loc))

config = get_config()

class Inferencer(object):
    def __init__(self):
        self.model = self.open_model()
    
    def open_model(self):
        model = TimeRNN(bat_size=1,in_features=3,h_size=1,layer_amnt=1)
        model.load_state_dict(torch.load(config['model_save_loc']))
        #model = torch.load(config['model_save_loc'])
        model.eval()
        return model

    def un_normalize(self,norm_val,min_val,max_val,typelist=None):
        if(typelist):
            for idx,item in enumerate(norm_val):
                new_val = item * (max_val - min_val) + min_val
                norm_val[idx] = new_val
            return norm_val
        else:
            return norm_val * (max_val - min_val) + min_val 

    def inference(self,value, normalize_method, model,minimum_price,maximum_price):
        value = np.array(value)
        predictions = []
        for sample in value:
            sample = np.array(sample).reshape(1,-1)
            example = torch.tensor(normalize_method.transform(sample)).float()
            
            if(str(device) == 'cuda'):
                example = example.to(device)

            output = model(example)
            output_unnorm = self.un_normalize(norm_val=output.detach(),min_val=minimum_price,max_val=maximum_price)
            predictions.append(output_unnorm)
        return predictions

    def fetch_latest_BTC_JSON(self):
        """Fetch the latest JSON data"""
        API_LINK = 'https://www.alphavantage.co/query?function=DIGITAL_CURRENCY_DAILY&symbol=BTC&market=USD&apikey=SAITMI5ZUMGEKGKY'
        page = requests.get(API_LINK).json()
        return page
    def parse_alphaV_JSON(self,raw_data):
        # Remove meta data for now
        raw_data.pop('Meta Data',None)
        # Remove key name
        df = pd.DataFrame.from_dict(raw_data['Time Series (Digital Currency Daily)'],dtype=float)
        # Flip dates as columns into rows
        df = df.transpose()
        return df

    def prediction_visualize(self,save=False,window=0,test_vals=[],pred_values=[],inference_values=[]):
        if(window == 0):
            plt.close()
            # --- visualize ---
            f,arr = plt.subplots()
            arr.plot(test_vals,'#FFA500')
            arr.plot(pred_values,'g')

            x_val = np.arange(len(pred_values),len(pred_values)+len(inference_values),1)
            # -- Connect --
            x = [x_val[0] - 1, x_val[0]]
            y = [pred_values[-1],inference_values[0]]
            arr.plot(x,y,'r')
            
            arr.plot(x_val,inference_values,'r')
            arr.grid()
            
            if(save):
                plt.savefig(fname='images/prediction.png')
        else:
            plt.close()
            test_vals = test_vals[-window:]
            pred_vals = pred_values[-window:]

            f,arr = plt.subplots(figsize=(10,10))
            #plt.figure(figsize=(10,10))
            arr.plot(test_vals,'#FFA500')
            arr.plot(pred_vals,'g')

            x_val = np.arange(len(pred_vals),len(pred_vals)+len(inference_values),1)
            # -- Connect --
            x = [x_val[0] - 1, x_val[0]]
            y = [pred_values[-1],inference_values[0]]
            arr.plot(x,y,'r--')

            arr.plot(x_val,inference_values,'r--')
            arr.grid()

            start = min( np.min(test_vals),np.min(pred_vals),np.min(inference_values))
            end = max(( np.max(test_vals),np.max(pred_vals),np.max(inference_values)))
        
            plt.yticks(np.arange(start-100,end+100,100))
            arr.yaxis.tick_right()
            arr.set_title(str(window) + ' day BTCUSD Price Prediction')
            arr.legend(['Actual Value','Predicted Value','Inference'],prop={'size': 15})
            if(save):
                plt.savefig(fname='images/prediction.png')

    def get_previous_data(self):
        pass

def main():

    inf = Inferencer()

    histPriceDay = cryptocompare.get_historical_price_day('BTC', curr='USD')

    # Getting CryptoCompare BTC volume data -- 2000 API calls back 
    vol = []
    for idx, item in enumerate(histPriceDay['Data']):
        vol.append(item['volumefrom']) 

    raw_data = inf.fetch_latest_BTC_JSON()
    df = inf.parse_alphaV_JSON(raw_data=raw_data)
    prices = np.array(df['4a. close (USD)'].tolist())
    data_df_temp = df.drop(labels=['1a. open (USD)','1b. open (USD)','2b. high (USD)','3b. low (USD)','4a. close (USD)','4b. close (USD)','6. market cap (USD)'],axis=1) # ,'2a. high (USD)','3a. low (USD)'
    minmax_2 = MinMaxScaler(data=data_df_temp.values)
    data_df_temp = pd.DataFrame(minmax_2.fit_transform(), columns=data_df_temp.columns)

    minimum_price = np.min(prices)
    maximum_price = np.max(prices)

    output = inf.inference(value=[ [11000,11880,vol[-1]]],
                       normalize_method=minmax_2,
                       model=inf.model,
                       minimum_price=minimum_price,
                       maximum_price=maximum_price
                      )
    print('BTC prediction: ', output)

    # -- Load previous training session data --
    test_data = np.load('utils/test_data.npy')
    train_preds = np.load('utils/predictions.npy')
    #print('test_data= ',test_data)
    #print('train_preds= ', train_preds)	
    test_data = inf.un_normalize(norm_val=test_data,min_val=minimum_price,max_val=maximum_price,typelist=True)
    inf.prediction_visualize(save=True,
                             window=30,
                             test_vals=test_data,
                             pred_values=train_preds,
                             inference_values=output)
    
if __name__ == '__main__':
    main()
