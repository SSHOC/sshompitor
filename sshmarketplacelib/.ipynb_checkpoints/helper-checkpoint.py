'''
Created on Nov 16, 2021

@author: cesare
'''
import pandas as pd
import requests
import re
import pickle
import os.path
import os
import json
import numpy as np
import yaml
import multiprocessing
from multiprocessing.pool import Pool
import errno

from . import mpdata as mpd

class Util(object):

    def __init__(self):
        '''
        Constructor
        '''
        if (os.path.isdir('data/')):
            self.datadir='data/';
        else:
            if (os.path.isdir('../data/')):
                self.datadir='../data';
            else:
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), "data")
        
        
        if (os.path.isfile('config.yaml')):
            self.configfile="config.yaml"
        else:
            if (os.path.isfile('../config.yaml')):
                self.configfile="../config.yaml"
            else:
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), "config.yaml")
        
        try:
            with open(self.configfile, 'r') as stream:
                try:
                    self.conf=yaml.safe_load(stream)
                except yaml.YAMLError as exc:
                    print(exc)
        except FileNotFoundError:
            print('Warning config.yaml file not present! Please create it and set the values, store it in the main directory')
        self.MPAPIserver=self.conf['API']['SERVER']
        self.MPserver=self.conf['MARKETPLACE']['SERVER']
        self.server=self.conf['MARKETPLACE']['SERVER']
        self.userId=self.conf['API']['USER']
        self.passW=self.conf['API']['PASSWORD']
        self.allCategories=self.conf['CATEGORIES']
        self.dataset_entrypoints=self.conf['DATASET_ENTRYPOINTS']
        for key, value in self.dataset_entrypoints.items():   
            self.dataset_entrypoints[key] = self.MPAPIserver+value
        self.empty_description=self.conf['EMPTY_DESCRIPTION_VAL']
        self.list_of_properties_url=self.conf['DATASET_ENTRYPOINTS']['list_of_properties']
        self.url_all_properties=['accessibleAt','terms-of-use-url', 'access-policy-url', 'privacy-policy-url', 'see-also', 'user-manual-url', 'service-level-url', 'thumbnail']
        self.url_dynamic_properties=['terms-of-use-url', 'access-policy-url', 'privacy-policy-url', 'see-also', 'user-manual-url', 'service-level-url', 'thumbnail']

        
            
        json_properties=pd.read_json(self.list_of_properties_url, orient='columns')
        df_properties= pd.json_normalize(json_properties['propertyTypes'])
        self.dynamic_properties=df_properties['code'].to_list()
        
        self.acceptedops=['=','<','>']
        
        
    def _getMPUrl(self, dataset):
        if isinstance(dataset, pd.DataFrame):
            if dataset.empty:
                print ("Error in building MPUrl: a non empty dataframe is required")
                return
        else:
            print ("Error: a dataframe is required!")
        if 'category' in dataset.columns:
            #print (dataset.columns)
            dataset['tempurl'] = dataset['category'].apply(lambda y: y+'/')
        else:
            if 'externalIds' in dataset.columns:
                dataset['tempurl'] = dataset['id'].apply(lambda y: str(y))
                
        #print (dataset['tempurl'])
        if 'MPUrl' in dataset.columns:
            dataset=dataset.drop(columns="MPUrl", axis=1)
        
        if 'persistentId' in dataset.columns:
            dataset.insert(0, 'MPUrl', dataset.tempurl+dataset['persistentId'])
        else:
            if 'id' in dataset.columns:
                dataset.insert(0, 'MPUrl', 'actors/'+dataset.tempurl)
                
        if 'tempurl' in dataset.columns:
            dataset=dataset.drop(columns='tempurl',axis=1)
        return dataset
    
    def getAllItemsBySources(self ):
        
        """
        
        Returns the number of items provided by every source.
        
        """
        
        dfs=[]
        for key in self.dataset_entrypoints:
            if os.path.isfile(self.datadir+key+'.pickle') and not key=='actors':
                temp= pd.read_pickle(self.datadir+key+'.pickle')
                category=temp.columns[-1]
                items= pd.json_normalize(temp[category])
                dfs.append(items)
        df_items= pd.concat(dfs, ignore_index=True)
        a_sources=df_items
        #a_sources=df_items.drop_duplicates(['source.label','label'])
        a_sources['source.label']= a_sources['source.label'].apply(lambda y: 'NA' if pd.isnull(y) else y )
        df_item_sources = a_sources['source.label'].value_counts()
        return df_item_sources
    
    def getItemsBySources(self, itemscategory):
        
        """
        
        Returns the number of items provided by every source for a specific category.
        
        Parameters:
        -----------
        
        itemcategory : String
            The category
        
        """
        
        dfs=[]
        if os.path.isfile(self.datadir+itemscategory+'.pickle'):
            temp= pd.read_pickle(self.datadir+itemscategory+'.pickle')
            category=temp.columns[-1]
            items= pd.json_normalize(temp[category])
        else:
            print('Not loaded or empty dataset: '+itemscategory)
            return pd.DataFrame()
        df_items= items
        if df_items.empty:
            print('Empty dataset')
            return pd.DataFrame()
        a_sources=df_items
        #a_sources=df_items.drop_duplicates(['source.label','label'])
        df_item_sources = a_sources['source.label'].value_counts()
        return df_item_sources
    
    def getCategoriesBySources(self):
        
        """
        
        Returns the number of items for every category provided by every data source.
        
        
        """
        
        dfs=[]
        dfs=[]
        for key in self.dataset_entrypoints:
            if os.path.isfile(self.datadir+key+'.pickle') and not key=='actors':
                temp= pd.read_pickle(self.datadir+key+'.pickle')
                category=temp.columns[-1]
                items= pd.json_normalize(temp[category])
                dfs.append(items)
        df_items= pd.concat(dfs, ignore_index=True)
        
        
        df_items_abs=df_items.groupby(['category', 'source.label']).count()['label'].unstack('category')
        
        df_items_abs=df_items_abs.T
        df_items_abs=df_items_abs.fillna(0)
        df_items_abs=df_items_abs.round()
       
        
        df_items_abs.index.names = ['Categories']
        return df_items_abs
    
    def getContributors(self):
        
        """
        
        Returns the contributors of items stored in the local dataset.
        
        """
        
        dfs=[]
        
        for key in self.dataset_entrypoints:
            
            if os.path.isfile('data/'+key+'.pickle') and not key=='actors' and not key=='list_of_properties' and not key=='login':
                print(f'Loading Actors for {key}')
                temp= pd.read_pickle('data/'+key+'.pickle')
                category=temp.columns[-1]
                items= pd.json_normalize(data=temp[category], record_path='contributors', meta=['label', 'persistentId', 'category'])
                dfs.append(items)
            else:
                if not key=='actors' and not key=='list_of_properties' and not key=='login':
                    print(f'{key} data is not present, skip...')
                
        df_items= pd.concat(dfs, ignore_index=True)
        cols = df_items.columns.tolist()
        cols = cols[-3:] + cols[:-3]
        df_items=df_items[cols]
        return df_items
    
    def getAllProperties(self):
        
        """
        
        Returns all the properties of items stored in the local dataset.
        
        
        """
        
        dfs=[]
        for key in self.dataset_entrypoints:
            if os.path.isfile('data/'+key+'.pickle') and not key=='actors':
                temp= pd.read_pickle('data/'+key+'.pickle')
                category=temp.columns[-1]
                items= pd.json_normalize(data=temp[category], record_path='properties', meta_prefix='ts_', meta=['label', 'persistentId', 'category'])
                dfs.append(items)
        df_items= pd.concat(dfs, ignore_index=True)
        if df_items.empty:
            print('Empty dataset')
            return pd.DataFrame()
        df_items['type.allowedVocabularies'] = df_items['type.allowedVocabularies'].apply(lambda y: np.nan if len(y)==0 else y)
        return df_items
    
    
    
    
    def getProperties(self, dataset=''):
        
        """
        
        Returns all the properties of items stored in the given dataset.
        
        Parameters:
        -----------
        
        dataset : DataFrame
            The dataset where the properties are searched
        
        """
        returned_values=['id', 'category', 'label', 'persistentId', 'accessibleAt', 'description', 'relatedItems', 'media', 'source.label', 'source.url',
                         'type.code', 'type.label', 'type.type', 'type.groupName', 'type.allowedVocabularies', 'concept.code', 'concept.vocabulary.code',
                         'concept.vocabulary.scheme', 'concept.vocabulary.namespace', 'concept.vocabulary.label', 'concept.vocabulary.closed',
                         'concept.label', 'concept.notation', 'concept.uri', 'concept.candidate', 'value', 'concept.definition']
        dfs=[]
        for key in self.dataset_entrypoints:
            if os.path.isfile('data/'+key+'.pickle') and not key=='actors':
                temp= pd.read_pickle('data/'+key+'.pickle')
                category=temp.columns[-1]
                items= pd.json_normalize(data=temp[category], record_path='properties', meta_prefix='ts_', meta=['label', 'persistentId', 'category'])
                dfs.append(items)
        df_items= pd.concat(dfs, ignore_index=True)
        if isinstance(dataset, pd.DataFrame):
            if not dataset.empty:
                df_list_of_properties_sources_subset=pd.merge(left=dataset, right=df_items, left_on='persistentId', right_on='ts_persistentId')
                if 'source.label_x' in df_list_of_properties_sources_subset.columns:
                    df_list_of_properties_sources_subset.rename(columns = {'source.label_x': 'source.label', 'ts_label':'label'}, inplace = True)
                return df_list_of_properties_sources_subset[returned_values]
            
        df_items['type.allowedVocabularies'] = df_items['type.allowedVocabularies'].apply(lambda y: np.nan if len(y)==0 else y)
        df_items.rename(columns = {'ts_persistentId': 'persistentId', 'ts_label':'label', 'ts_category':'category'}, inplace = True)
        return df_items
    
    
    def getAllPropertiesBySources(self):
        
        """
        
        Returns all dynamic properties stored in the local datasets. For every dinamyc property it is reported also
        the main attributes of the item whom it belongs.
        
        
        """
        
        df_temp_items=[]
        df_temp_properties=[]
        for key in self.dataset_entrypoints:
            if os.path.isfile(self.datadir+key+'.pickle') and not key=='actors':
                temp= pd.read_pickle(self.datadir+key+'.pickle')
                category=temp.columns[-1]
                items= pd.json_normalize(temp[category])
                properties= pd.json_normalize(data=temp[category], record_path='properties', meta_prefix='ts_', meta=['label'])
                df_temp_items.append(items)
                df_temp_properties.append(properties)
                df_items= pd.concat(df_temp_items, ignore_index=True)
                df_properties=pd.concat(df_temp_properties, ignore_index=True)
        if (not df_items.empty) and (not df_properties.empty):
            my_tmp=df_items[['persistentId','label', 'source.label', 'category', 'status']]
            df_list_of_properties_sources=pd.merge(left=df_properties, right=my_tmp, left_on='ts_label', right_on='label')
        else:
            return (pd.DataFrame())
        df_list_of_properties_sources=self._getMPUrl(df_list_of_properties_sources)
        return df_list_of_properties_sources #[self.returned_values]
    
    
    
    def getPropertiesValuesFrequency(self, itemscategory, propertyname):
        dfs=[]
        if os.path.isfile(self.datadir+itemscategory+'.pickle'):
            temp= pd.read_pickle(self.datadir+itemscategory+'.pickle')
            category=temp.columns[-1]
            items= pd.json_normalize(data=temp[category], record_path='properties', meta_prefix='ts_', meta=['label'])
        else:
            return(pd.DataFrame())
        df_items= items
        df_items['type.allowedVocabularies'] = df_items['type.allowedVocabularies'].apply(lambda y: np.nan if len(y)==0 else y)
        if propertyname not in list(df_items.columns):
            return (pd.DataFrame())
        df_items_values = df_items[propertyname].value_counts()
        return df_items_values
    
    #TO BE REMOVED, DO NOT USE IT!
    def getDuplicates(self, dataset, props=''):
        
        """
        
        Returns all the items of dataset having duplicated values in 
        the properties/attributes defined in the props parameter.
        
        Parameters:
        -----------
        
        dataset : DataFrame
            The dataset where the duplicates are searched
        props: String (optional)
            The property/attribute or list of properties/attributes to be used as filter
            
        """
        
        list_columns=[]
        if 'accessibleAt' in dataset.columns:
            a = (dataset[['label','accessibleAt']].applymap(type) == list).all()
            list_columns = a.index[a].tolist()
        else:
            if 'actor.externalIds' in dataset.columns:
                a = (dataset[['actor.name', 'actor.affiliations']].applymap(type) == list).all()
                list_columns = a.index[a].tolist()
            if 'externalIds' in dataset.columns:
                a = (dataset[['name', 'affiliations']].applymap(type) == list).all()
                list_columns = a.index[a].tolist()
        
        if isinstance(dataset, pd.DataFrame):
            if dataset.empty:
                print ("Error: a not empty dataframe is required")
                return
        else:
            print ("Error: a dataframe is required!")
        if props.strip()!='':
            properties=props.replace(" ", "").split(',')
            for attr in properties:
                if not attr in dataset.columns:
                    print (f"Error: {attr} not a valid attribute")
                    return
            dataset=self._getMPUrl(dataset)
            for attrib in properties:
                if attrib in list_columns:
                    dataset=dataset.explode(attrib)
            df_tool_work_duplicates=dataset[dataset.duplicated(subset=properties, keep=False)]
        else:
            df_tool_work_duplicates=dataset[dataset.astype(str).duplicated(subset= None, keep=False)]
            
        return df_tool_work_duplicates.drop_duplicates(subset = ['id'], keep = False).reset_index(drop = True)
    
    
    def getDuplicatedActorsWithItems(self, dataset, props=''):
        
        """
        
        Returns all the actors of dataset having duplicated values in 
        the properties/attributes defined in the props parameter that has at least one associated item.
        
        Parameters:
        -----------
        
        dataset : DataFrame
            The dataset where the duplicates are searched
        props: String (optional)
            The property/attribute or list of properties/attributes to be used as filter
            
        """
        
        if isinstance(dataset, pd.DataFrame):
            if dataset.empty:
                print ("Error: a not empty dataframe is required")
                return
        else:
            print ("Error: a dataframe is required!")
            return
        if props.strip()!='':
            properties=props.replace(" ", "").split(',')
            for attr in properties:
                if not attr in dataset.columns:
                    print (f"Error: {attr} not a valid attribute")
                    return
        extcontr_df=self.getContributors()
        test_tmp=pd.merge(left=dataset, right=extcontr_df[['persistentId', 'label', 'category','actor.id','role.label']], left_on='id', right_on='actor.id')
        testdup=test_tmp[test_tmp.duplicated(subset=properties, keep=False)]
        testdup=testdup[['MPUrl', 'id', 'name', 'externalIds','affiliations','website','role.label','persistentId','label','category']]
        df_tmp=testdup.groupby('name')['id'].apply(set).reset_index(name='Id')
        df_tmp['isDuplicated']=df_tmp['Id'].apply(lambda y: 'yes' if len(y)>1 else 'no')
        df_tmpduplicated=df_tmp[df_tmp.isDuplicated=='yes']
        tmp_ex=df_tmpduplicated.explode('Id')
        test_te=tmp_ex[['Id', 'isDuplicated']]
        test_res=pd.merge(left=test_te, right=testdup, left_on='Id', right_on='id')
        test_res=test_res.drop(columns='Id',axis=1)
        test_res['item']=test_res.category+'/'+test_res.persistentId
        test_set=test_res.groupby(['MPUrl', 'id', 'name'])['item'].apply(list).reset_index(name='itemPersistentId')
        return test_res, test_set.sort_values('name')


    
    
    def getNullValues(self, props=""):
        
        """
        
        Returns the total number of null values for a list of properties/attributes in the local dataset.
        
        Parameters:
        -----------
        
        props: String (optional)
            The property/attribute or list of properties/attributes to be checked. If it is empty or
            not set the numbers of null values for all the properties/attributes are returned.
            
        """
        
        dfs=[]
        properties=[]
        if props.strip()!='':
            properties=props.replace(" ", "").split(',')
            
        for key in self.dataset_entrypoints:
            #print (key)
            if os.path.isfile(self.datadir+key+'.pickle') and not key=='actors':
                temp= pd.read_pickle(self.datadir+key+'.pickle')
                category=temp.columns[-1]
                items= pd.json_normalize(temp[category])
                dfs.append(items)
        df_items= pd.concat(dfs, ignore_index=True)
        temp_ed_str=self.empty_description.replace(".","")
        df_items = df_items.replace(self.empty_description, np.nan)
        df_items = df_items.replace(temp_ed_str, np.nan)
        df_items.contributors = df_items.contributors.apply(lambda y: np.nan if len(y)==0 else y)
        #df_items.licenses = df_items.licenses.apply(lambda y: np.nan if len(y)==0 else y)
        df_items.externalIds = df_items.externalIds.apply(lambda y: np.nan if len(y)==0 else y)
        #print('pippo')
        
        df_items.accessibleAt = df_items.accessibleAt.apply(lambda y: np.nan if len(y)==0 else y)
        df_items.relatedItems = df_items.relatedItems.apply(lambda y: np.nan if len(y)==0 else y)
        
        df_items.properties = df_items.properties.apply(lambda y: np.nan if len(y)==0 else y)
        df_items.media = df_items.media.apply(lambda y: np.nan if len(str(y))==0 else y)
        
        #dynamic properties
        df_prop_data=self.getAllProperties()
        df_prop_data.value = df_prop_data.value.apply(lambda y: np.nan if y is None else y)
        df_prop_data['type.groupName'] = df_prop_data['type.groupName'].apply(lambda y: np.nan if y is None else y)
        df_prop_data['concept.vocabulary.label'] = df_prop_data['concept.vocabulary.label'].apply(lambda y: np.nan if y=='' else y)
        df_prop_data['concept.notation'] = df_prop_data['concept.notation'].apply(lambda y: np.nan if y=='' else y)
        df_prop_data['concept.definition'] = df_prop_data['concept.definition'].apply(lambda y: np.nan if y=='' else y)
    
        df_prop_data=df_prop_data.reset_index()
        df_prop_data.drop_duplicates(subset=['ts_persistentId', 'type.code'], keep='last', inplace = True)
        df_items=df_items.reset_index()
        test=df_prop_data
        for pr in df_prop_data.columns:
            if pr !='ts_persistentId':
                #print ('pr '+pr)
                df_prop_data_tmp=df_prop_data.groupby('ts_persistentId')[pr].apply(list).reset_index(name='temp')
                df_prop_data_tmp[pr]=df_prop_data_tmp.temp.apply(lambda y: np.nan if pd.isnull(y).all() else y)
                df_prop_data_tmp=df_prop_data_tmp.drop(columns='temp',axis=1)
                df_items=pd.merge(df_items, df_prop_data_tmp, left_on='persistentId',right_on='ts_persistentId', how = 'outer', suffixes=('', '_right')).fillna(np.nan)
                
        # here dynamic properties
        not_found_properties=[]
        for pr in properties:
            
            if pr in self.dynamic_properties:
                #print ('>>>'+pr)
                myd=df_prop_data[df_prop_data['type.code']==pr]
                if not myd.empty:
                    tmp_or=myd[['ts_persistentId', 'type.code']]
                    tmp=tmp_or.rename(columns = {'type.code': pr}, inplace=False)
                    #display(tmp)
                    #display(df_items)
                    df_items=pd.merge(left=df_items, right=tmp, left_on='persistentId', right_on='ts_persistentId', how = 'outer', suffixes=('', '_right')).fillna(np.nan)
                    #print (df_items.shape)
                   
                else:
                    not_found_properties.append(pr)
        for nfo in not_found_properties:
            properties.remove(nfo)
        #df_items['null.version']= df_items['version'].isnull().groupby(pippo.category).transform('sum').astype(int)
        #df_items['null.label']= df_items['label'].isnull().groupby(pippo.category).transform('sum').astype(int)
        
        df_items_abs=df_items[df_items.columns.difference(['category'])].isnull().groupby(df_items.category).sum().astype(int)
        df_items_ratio=df_items[df_items.columns.difference(['category'])].isnull().groupby(df_items.category).apply(lambda x: x.sum()*100/len(x))#.sum()*100/len(df_items)#.astype(int)
        
        #df.groupby('group').apply(lambda x: x.value.isnull().sum()/len(x))
        df_items_ratio=df_items_ratio.round(decimals=2)
        if properties and properties[0].strip()!='':
            for pr in properties:
                if pr not in df_items_abs.columns:
                    print (f'Wrong parameter: {pr} is not a valid property name \n')
                    return
            df_items_ratio=df_items_ratio[properties]
            df_items_abs=df_items_abs[properties]
        if 'id_x' in df_items_abs.columns:
            df_items_abs=df_items_abs.drop(columns='id_x',axis=1)
            df_items_ratio=df_items_ratio.drop(columns='id_x',axis=1)
        if 'id_y' in df_items_abs.columns:
            df_items_abs=df_items_abs.drop(columns='id_y',axis=1)
            df_items_ratio=df_items_ratio.drop(columns='id_y',axis=1)
        if 'index_x' in df_items_abs.columns:
            df_items_abs=df_items_abs.drop(columns='index_x',axis=1)
            df_items_ratio=df_items_ratio.drop(columns='index_x',axis=1)
        if 'index_y' in df_items_abs.columns:
            df_items_abs=df_items_abs.drop(columns='index_y',axis=1)
            df_items_ratio=df_items_ratio.drop(columns='index_y',axis=1)
        df_items_abs=df_items_abs.T
        df_items_ratio=df_items_ratio.T
        df_items_abs.index.names = ['property: missed values']
        df_items_ratio.index.names = ['property: missed values (%)']
        return df_items_abs, df_items_ratio, test
    
    
    def getItemsWithNullValues(self, props, all=True):
        
        """
        
        Returns the items in the local dataset having null values for a list of properties/attributes.
        
        Parameters:
        -----------
        
        props: String
            The property/attribute or list of properties/attributes to be checked. If it is empty or
            not set the numbers of null values for all the properties/attributes are returned.
        
        all: boolean (optional)
            If 'True' (default) the items where all the properties/attributes are null are returned, 
            if ' False' the items where at least one of the properties/attributes are null are returned
            
        """
        
        dfs=[]
        properties=[]
        if props.strip()!='':
            properties=props.replace(" ", "").split(',')
        else:
            print ("A list of properties must be defined")
            return
            
        for key in self.dataset_entrypoints:
            if os.path.isfile(self.datadir+key+'.pickle') and not key=='actors':
                temp= pd.read_pickle(self.datadir+key+'.pickle')
                category=temp.columns[-1]
                items= pd.json_normalize(temp[category])
                dfs.append(items)
        df_items= pd.concat(dfs, ignore_index=True)
        temp_ed_str=self.empty_description.replace(".","")
        df_items = df_items.replace(self.empty_description, np.nan)
        df_items = df_items.replace(temp_ed_str, np.nan)
        #df_items.licenses = df_items.licenses.apply(lambda y: np.nan if len(y)==0 else y)
        df_items.externalIds = df_items.externalIds.apply(lambda y: np.nan if len(y)==0 else y)
        df_items.contributors = df_items.contributors.apply(lambda y: np.nan if len(y)==0 else y)
        df_items.accessibleAt = df_items.accessibleAt.apply(lambda y: np.nan if len(y)==0 else y)
        df_items.relatedItems = df_items.relatedItems.apply(lambda y: np.nan if len(y)==0 else y)
        df_items.properties = df_items.properties.apply(lambda y: np.nan if len(y)==0 else y)
        df_items.media = df_items.media.apply(lambda y: np.nan if len(y)==0 else y)
        #dynamic properties
        df_prop_data=self.getAllProperties()
        df_prop_data.value = df_prop_data.value.apply(lambda y: np.nan if y is None else y)
        df_prop_data['type.groupName'] = df_prop_data['type.groupName'].apply(lambda y: np.nan if y is None else y)
        df_prop_data['concept.vocabulary.label'] = df_prop_data['concept.vocabulary.label'].apply(lambda y: np.nan if y=='' else y)
        df_prop_data['concept.notation'] = df_prop_data['concept.notation'].apply(lambda y: np.nan if y=='' else y)
        df_prop_data['concept.definition'] = df_prop_data['concept.definition'].apply(lambda y: np.nan if y=='' else y)
    
        df_prop_data=df_prop_data.reset_index()
        df_prop_data.drop_duplicates(subset=['ts_persistentId', 'type.code'], keep='last', inplace = True)
        df_items=df_items.reset_index()
        if props.strip()!='':
            properties=props.replace(" ", "").split(',')
        if properties and properties[0].strip()!='':
            for pr in properties:
                if (pr not in df_items.columns) & (pr not in df_prop_data.columns) & (pr not in self.dynamic_properties):
                    print (f'Wrong parameter: {pr} is not a valid property name \n')
                    return
        for pr in properties:
            if pr in df_prop_data.columns:
                df_prop_data_tmp=df_prop_data.groupby('ts_persistentId')[pr].apply(list).reset_index(name='temp')
                df_prop_data_tmp[pr]=df_prop_data_tmp.temp.apply(lambda y: np.nan if pd.isnull(y).all() else y)
                df_prop_data_tmp=df_prop_data_tmp.drop(colums='temp',axis=1)
                df_items=pd.merge(df_items, df_prop_data_tmp, left_on='persistentId',right_on='ts_persistentId', how = 'outer').fillna(np.nan)
        # here dynamic properties
        not_found_properties=[]
        for pr in properties:
            if pr in self.dynamic_properties:
                #print ('pr '+pr)
                myd=df_prop_data[df_prop_data['type.code']==pr]
                if not myd.empty:
                    #print (' here '+pr)
                    tmp=myd[['ts_persistentId', 'type.code']]
                    #tmp.rename(columns = {'type.code': pr}, inplace=True)
                    df_items=pd.merge(left=df_items, right=tmp, left_on='persistentId', right_on='ts_persistentId', how = 'outer', suffixes=('', '_y')).fillna(np.nan)
                    df_items.rename(columns = {'type.code': pr}, inplace=True)
                else:
                    
                    not_found_properties.append(pr)
                    df_items[pr]=np.nan
    #     for nfo in not_found_properties:
    #         properties.remove(nfo)
                           
        df_items_mask=df_items[properties].apply(lambda x: x.isnull())
        if all:
            df_items=df_items[df_items_mask.all(axis=1)]
        else:
            df_items=df_items[df_items_mask.any(axis=1)]
        df_items['tempurl'] = df_items['category'].apply(lambda y: y+'/' if len(y)>0 else y)
        df_items['MPUrl']=df_items['tempurl']+df_items['persistentId']
        df_items=df_items.drop(columns='tempurl',axis=1)
        return df_items
    
    #rendering functions
    
    def make_clickable(self, val):
    # target _blank to open new window
        return '<a target="_blank" href="'+self.MPserver+'{}">{}</a>'.format(val, val)
    
    
    def lists_to_list(self, nested_lists):
        outer_list = []
        #print (f'input {nested_lists}')
        for el in nested_lists:
           
            if type(el) == list: 
                self.lists_to_list(el)
            else:
                
                if type(el) == dict:
                    
                    jsel=json.dumps(el, sort_keys=True)
                    outer_list.append(jsel)
                else:
                    
                    outer_list.append(el)
        #print (f' output {set(outer_list)}')
        return set(outer_list)
    
    
    #get related items
    
    def getRelatedItems(self, itemcategories, *nrelitems):
        returned_fields=['MPUrl','persistentId', 'category', 'label', 'relation.label',  'relitem_persistentId', 'relItem_category', 'relItem_label', 'relItem_description', 'relation.code', 'value']
        wid=['workflowId']
        no_rel_items_fields=['MPUrl','persistentId', 'category', 'label', 'relatedItems', 'value']
        dfs=[]

        no_related_items=pd.DataFrame()
        if itemcategories.strip()=='all':
                categories=self.allCategories
        else:
            if itemcategories.strip()!='':
                categories=itemcategories.replace(" ", "").split(',')
                for ca in categories:
                    if ca.strip() not in self.allCategories:
                        print ('Wrong Category: '+ca)
            else:
                print ('No category defined!')
                return
        for cate in categories:
            if os.path.isfile('data/'+cate+'.pickle'):
               
                temp= pd.read_pickle('data/'+cate+'.pickle')
                category=temp.columns[-1]
                items= pd.json_normalize(temp[category])
                if not nrelitems:
                    selected_items=items[items['relatedItems'].map(len)>0]
                else:
                    if type(nrelitems[0])==int and len (nrelitems)==1:
                        nval=nrelitems[0]
                        l = list(nrelitems)
                        l.insert(1, nval)
                        l[0]='>'
                        nrelitems=tuple(l)
                    
                    if type(nrelitems[0])!=int and len (nrelitems)==1:
                        l = list(nrelitems)
                        l.insert(1, 0)
                        l[0]='>'
                        nrelitems=tuple(l)
                        
                    if nrelitems[0] not in self.acceptedops or len (nrelitems)>2:
                        print('wrong parameters ')
                        return
                    if (nrelitems[0].strip()=='=' and nrelitems[1]<1) or (nrelitems[0].strip()=='<' and nrelitems[1]==1):
                        #print (items['relatedItems'])
                        items['value']=items['relatedItems'].map(len)
                        no_related_items=items[items['relatedItems'].map(len)==0]
                        
                        
                        #return selected_items[['persistentId', 'category', 'label', 'relatedItems']]
                    if nrelitems[0].strip()=='=' and nrelitems[1]>0:
                        #print (nrelitems[1])
                        selected_items=items[items['relatedItems'].map(len)==nrelitems[1]]
                    if nrelitems[0].strip()=='>':
                        selected_items=items[items['relatedItems'].map(len)>nrelitems[1]]
                    if nrelitems[0].strip()=='<' and nrelitems[1]>1:
                        selected_items=items[items['relatedItems'].map(len)<nrelitems[1]]
                        
                items= pd.json_normalize(data=temp[category], record_path='relatedItems', meta_prefix='item_', meta=['label', 'persistentId', 'category'])
                #print (category)
                if no_related_items.empty:
                    selected_items['value']=selected_items['relatedItems'].map(len)
                    
                    searched_items=pd.merge(left=selected_items, right=items, left_on='persistentId', right_on='item_persistentId')
                    
                    if not searched_items.empty:
                        dfs.append(searched_items)


                else:
                    dfs.append (no_related_items)
                    returned_fields=no_rel_items_fields
        if not dfs:
            print ('getRelatedItems(itemcategories, *nrelitems): no values found')
            return pd.DataFrame(columns=returned_fields)
        df_items= pd.concat(dfs, ignore_index=True)
        #return df_items[['item_persistentId', 'item_category', 'item_label', 'relation.label',  'persistentId', 'category', 'label', 'workflowId', 'description', 'relation.code']]
        df_items.rename(columns = {'item_persistentId': 'persistentId', 'item_category':'category', 'item_label':'label','persistentId_y': 'relitem_persistentId', 'category_y': 'relItem_category', 'label_y': 'relItem_label', 'description_y': 'relItem_description'}, inplace = True)
       
        if df_items.empty:
            print ('getRelatedItems(itemcategories, *nrelitems): no values found')
            return pd.DataFrame(columns=returned_fields)
        
            
        df_items=self._getMPUrl(df_items)
        #df_items['MPUrl'] = df_items['MPUrl'].apply(lambda y: y if len(y)>0 else y)
       
            
        if wid[0] in df_items.columns:
            returned_fields=returned_fields+wid    
    
        df_items=df_items[returned_fields].sort_values('label')
       
        df_items.reset_index(inplace=True)
        return df_items[returned_fields]
    
    def getAllRelatedItems(self):
        dfs=[]
        for key in self.dataset_entrypoints:
            if os.path.isfile(self.datadir+key+'.pickle') and not key=='actors':
                temp= pd.read_pickle(self.datadir+key+'.pickle')
                category=temp.columns[-1]
                items= pd.json_normalize(data=temp[category], record_path='relatedItems', meta_prefix='item_', meta=['label', 'persistentId', 'category'])
                dfs.append(items)
        df_items= pd.concat(dfs, ignore_index=True)
        #df_items['type.allowedVocabularies'] = df_items['type.allowedVocabularies'].apply(lambda y: np.nan if len(y)==0 else y)
        return df_items[['item_persistentId', 'item_category', 'item_label', 'relation.label',  'persistentId', 'category', 'label', 'workflowId', 'description', 'relation.code']]
    
        