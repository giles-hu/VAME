#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec  6 12:06:29 2019

@author: luxemk
"""

import os
import numpy as np

from pathlib import Path
import warnings
import matplotlib.cbook
warnings.filterwarnings("ignore",category=matplotlib.cbook.mplDeprecation)

from vame.util.auxiliary import read_config


def get_adjacency_matrix(labels, n_cluster):
    temp_matrix = np.zeros((n_cluster,n_cluster), dtype=np.float64)
    adjacency_matrix = np.zeros((n_cluster,n_cluster), dtype=np.float64)
    cntMat = np.zeros((n_cluster))
    steps = len(labels)
    
    for i in range(n_cluster):
        for k in range(steps-1):
            idx = labels[k]
            if idx == i:
                idx2 = labels[k+1]
                if idx == idx2:
                    continue
                else:
                    cntMat[idx2] = cntMat[idx2] +1
        temp_matrix[i] = cntMat
        cntMat = np.zeros((n_cluster))
    
    for k in range(steps-1):
        idx = labels[k]
        idx2 = labels[k+1]
        if idx == idx2:
            continue
        adjacency_matrix[idx,idx2] = 1
        adjacency_matrix[idx2,idx] = 1
        
    transition_matrix = get_transition_matrix(temp_matrix)
    
    return adjacency_matrix, transition_matrix


def get_transition_matrix(adjacency_matrix, threshold = 0.0):
    row_sum=adjacency_matrix.sum(axis=1)
    '''
    print('row sum')
    print(row_sum)
    print('row sum axis')
    print(row_sum[:,np.newaxis])
    '''
    transition_matrix = adjacency_matrix/row_sum[:,np.newaxis]
    transition_matrix[transition_matrix <= threshold] = 0
    if np.any(np.isnan(transition_matrix)):
            transition_matrix=np.nan_to_num(transition_matrix)
    return transition_matrix

    
def consecutive(data, stepsize=1):
    data = data[:]
    return np.split(data, np.where(np.diff(data) != stepsize)[0]+1)
    
    
def get_network(path_to_file, file, cluster_method, n_cluster):
    if cluster_method == 'kmeans':
        labels = np.load(path_to_file + '/'+str(n_cluster)+'_km_label_'+file+'.npy')
    else:
        labels = np.load(path_to_file + '/'+str(n_cluster)+'_gmm_label_'+file+'.npy')
        
    adj_mat, transition_matrix = get_adjacency_matrix(labels, n_cluster=n_cluster)       
    motif_usage = np.unique(labels, return_counts=True)
    cons = consecutive(motif_usage[0])
    '''
    if len(cons) != 1:
        usage_list = list(motif_usage[1])
        index = cons[0][-1]+1
        usage_list.insert(index,0)
    
        usage = np.array(usage_list)
    
        motif_usage = usage
    else:
        motif_usage = motif_usage[1]
    '''
    loop_num = 0
    while len(cons) != 1:
        usage_list = list(motif_usage[1])
        usage_index = list(motif_usage[0])
        if cons[0][0] > 0:
            index = 0
        else:
            index = cons[0][-1]+1
        usage_list.insert(index,0)
        usage_index.insert(index,index)   
        motif_usage = [np.array(usage_index) ,np.array(usage_list)]
        cons = consecutive(motif_usage[0])
        loop_num= loop_num + 1
#        if loop_num > n_cluster:
#            print('Unexpected error:'+ motif usage)
#            sys.exit(1)
        
        #print(cons)
        #print(len(cons))
    else:
        motif_usage = list(motif_usage[1])
    while len(motif_usage) < n_cluster:
        motif_usage = np.append(motif_usage,0)
    
    
    np.save(path_to_file+'/behavior_quantification/adjacency_matrix.npy', adj_mat)
    np.save(path_to_file+'/behavior_quantification/transition_matrix.npy', transition_matrix)
    np.save(path_to_file+'/behavior_quantification/motif_usage.npy', motif_usage)   

    
def behavior_quantification(config, model_name, cluster_method='kmeans', n_cluster=30):
    config_file = Path(config).resolve()
    cfg = read_config(config_file)
    
    files = []
    if cfg['all_data'] == 'No':
        all_flag = input("Do you want to quantify your entire dataset? \n"
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
    

    for file in files:
        print('Processing:' + file)
        path_to_file=cfg['project_path']+'results/'+file+'/'+model_name+'/'+cluster_method+'-'+str(n_cluster)
       
        if not os.path.exists(path_to_file+'/behavior_quantification/'):
            os.mkdir(path_to_file+'/behavior_quantification/')
        
        get_network(path_to_file, file, cluster_method, n_cluster)
        







   

