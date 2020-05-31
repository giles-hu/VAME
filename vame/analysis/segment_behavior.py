#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Nov  3 15:37:45 2019

@author: luxemk
"""

import os
import numpy as np
from pathlib import Path

import torch
import scipy.signal
from sklearn import mixture
from sklearn.cluster import KMeans

from vame.util.auxiliary import read_config
from vame.model.rnn_vae import RNN_VAE


def load_data(PROJECT_PATH, file, data):
    X = np.load(PROJECT_PATH+'data/'+file+'/'+file+data+'.npy')
    mean = np.load(PROJECT_PATH+'data/train/seq_mean.npy')
    std = np.load(PROJECT_PATH+'data/train/seq_std.npy') 
    X = (X-mean)/std
    return X
        

def kmeans_clustering(context, n_clusters):    
    kmeans = KMeans(init='k-means++',n_clusters=n_clusters, random_state=42,n_init=15).fit(context)
    return kmeans.predict(context)


def gmm_clustering(context,n_components):
    GMM = mixture.GaussianMixture
    gmm = GMM(n_components=n_components,covariance_type='full').fit(context)
    return gmm.predict(context)


def behavior_segmentation(config, model_name=None, cluster_method='kmeans', n_cluster=[30]):
    
    config_file = Path(config).resolve()
    cfg = read_config(config_file)
    if not os.path.exists(cfg['project_path']+'results'):
            os.mkdir(cfg['project_path']+'results')
    
    for folders in cfg['video_sets']: 
        if not os.path.exists(cfg['project_path']+'results'+os.sep+folders):
            os.mkdir(cfg['project_path']+'results'+os.sep +folders)
        if not os.path.exists(cfg['project_path']+'results'+os.sep+folders+os.sep +model_name):
            os.mkdir(cfg['project_path']+'results'+os.sep +folders+os.sep +model_name)
        
    files = []
    if cfg['all_data'] == 'No':
        all_flag = input("Do you want to qunatify your entire dataset? \n"
                         "If you only want to use a specific dataset type filename: \n"
                         "yes/no/filename ")
    else: 
        all_flag = 'yes'
    
    if all_flag == 'yes' or all_flag == 'Yes':
        for file in cfg['video_sets']:
            files.append(file)  
    elif all_flag == 'no' or all_flag == 'No':
        for file in cfg['video_sets']:
            use_file = input("Do you want to quantify " + file + "? yes/no: ")
            if use_file == 'yes':
                files.append(file)
            if use_file == 'no':
                continue
    else:
        files.append(all_flag)
     
    
    use_gpu = torch.cuda.is_available()
    if use_gpu:
        print("Using CUDA")
        print('GPU active:',torch.cuda.is_available())
        print('GPU used:',torch.cuda.get_device_name(0)) 
    else:
        print("CUDA is not working!")
        
    z, z_logger = temporal_quant(cfg, model_name, files, use_gpu) 
    cluster_latent_space(cfg, files, z, z_logger, cluster_method, n_cluster, model_name)
    
    
def temporal_quant(cfg, model_name, files, use_gpu):
    
    SEED = 19
    ZDIMS = cfg['zdims']
    FUTURE_DECODER = cfg['prediction_decoder']
    TEMPORAL_WINDOW = cfg['time_window']*2
    FUTURE_STEPS = cfg['prediction_steps']
    NUM_FEATURES = cfg['num_features']
    PROJECT_PATH = cfg['project_path']
    hidden_size_layer_1 = cfg['hidden_size_layer_1']
    hidden_size_layer_2 = cfg['hidden_size_layer_2']
    hidden_size_rec = cfg['hidden_size_rec']
    hidden_size_pred = cfg['hidden_size_pred']
    dropout_encoder = cfg['dropout_encoder']
    dropout_rec = cfg['dropout_rec']
    dropout_pred = cfg['dropout_pred']
    temp_win = int(TEMPORAL_WINDOW/2)
    
    if use_gpu:
        torch.cuda.manual_seed(SEED)
        model = RNN_VAE(TEMPORAL_WINDOW,ZDIMS,NUM_FEATURES,FUTURE_DECODER,FUTURE_STEPS, hidden_size_layer_1, 
                        hidden_size_layer_2, hidden_size_rec, hidden_size_pred, dropout_encoder, 
                        dropout_rec, dropout_pred).cuda()
    
    if cfg['snapshot'] == 'yes':
        model.load_state_dict(torch.load(cfg['project_path']+'/'+'model/best_model/snapshots/'+model_name+'_'+cfg['Project']+'_epoch_'+cfg['snapshot_epoch']+'.pkl'))
    else:
        model.load_state_dict(torch.load(cfg['project_path']+'/'+'model/best_model/'+model_name+'_'+cfg['Project']+'.pkl'))
    model.eval()
    
    z_list = []
    z_logger = []
    logger = 0
    for file in files:
        print("Computing latent space for %s " %file)
        z_logger.append(logger)
        
            
        data=cfg['load_data']
        X = load_data(PROJECT_PATH, file, data)
            
        if X.shape[0] > X.shape[1]:
                X=X.T
                
        num_frames = len(X[0,:]) - temp_win
        window_start = int(temp_win/2)
        idx = int(temp_win/2)
        x_decoded = []
        
        with torch.no_grad(): 
            for i in range(num_frames):
                if idx >= num_frames:
                    break
                data = X[:,idx-window_start:idx+window_start]
                data = np.reshape(data, (1,temp_win,NUM_FEATURES))
                dataTorch = torch.from_numpy(data).type(torch.FloatTensor).cuda()
                h_n = model.encoder(dataTorch)
                latent, _, _ = model.lmbda(h_n)
                z = latent.cpu().data.numpy()
                x_decoded.append(z)
                idx += 1
                
        z_temp = np.concatenate(x_decoded,axis=0)    
        logger_temp = len(z_temp)
        logger += logger_temp 
        z_list.append(z_temp)
    
    z_array= np.concatenate(z_list)
    z_logger.append(len(z_array))
    
    return z_array, z_logger
    

def cluster_latent_space(cfg, files, z_data, z_logger, cluster_method, n_cluster, model_name):
    
    for cluster in n_cluster:
        if cluster_method == 'kmeans':
            print('Behavior segmentation via k-Means for %d cluster.' %cluster)
            data_labels = kmeans_clustering(z_data, n_clusters=cluster)
            data_labels = np.int64(scipy.signal.medfilt(data_labels, cfg['median_filter']))
            
        if cluster_method == 'GMM':
            print('Behavior segmentation via GMM.')
            data_labels = gmm_clustering(z_data, n_components=cluster)
            data_labels = np.int64(scipy.signal.medfilt(data_labels, cfg['median_filter']))
            
        #save latent vector
        print("Saving latent vector..." )
        if not os.path.exists(cfg['project_path']+'results_latent'):
                os.mkdir(cfg['project_path']+'results_latent')
        
        np.save(cfg['project_path']+'results_latent'+os.sep+str(cluster)+'_zdata', z_data)
        np.save(cfg['project_path']+'results_latent'+os.sep+str(cluster)+'_zlogger', z_logger)
        if cluster_method == 'kmeans':
            np.save(cfg['project_path']+'results_latent'+os.sep+str(cluster)+'_km_label', data_labels)
        
        
        #
        for idx, file in enumerate(files):
            print("Segmentation for file %s..." %file )
            if not os.path.exists(cfg['project_path']+'results/'+file+'/'+model_name+'/'+cluster_method+'-'+str(cluster)):
                os.mkdir(cfg['project_path']+'results/'+file+'/'+model_name+'/'+cluster_method+'-'+str(cluster))
        
            save_data = cfg['project_path']+'results/'+file+'/'+model_name+'/'
            labels = data_labels[z_logger[idx]:z_logger[idx+1]-1]
            latent_v = z_data[z_logger[idx]:z_logger[idx+1]-1]

                
            if cluster_method == 'kmeans':
                np.save(save_data+cluster_method+'-'+str(cluster)+'/'+str(cluster)+'_km_label_'+file, labels)
                
            if cluster_method == 'GMM':
                np.save(save_data+cluster_method+'-'+str(cluster)+'/'+str(cluster)+'_gmm_label_'+file, labels)
            
            if cluster_method == 'all':
                np.save(save_data+cluster_method+'-'+str(cluster)+'/'+str(cluster)+'_km_label_'+file, labels)
                np.save(save_data+cluster_method+'-'+str(cluster)+'/'+str(cluster)+'_gmm_label_'+file, labels)
                
            # store z data
            np.save(save_data+cluster_method+'-'+str(cluster)+'/'+str(cluster)+'_latent_vector_'+file, latent_v)
    
    

