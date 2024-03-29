# -*- coding: utf-8 -*-
"""Recommendation Systems.ipynb

Dataset: https://www.kaggle.com/arashnic/book-recommendation-dataset

Ratings: https://an-utd-course.s3.us-west-1.amazonaws.com/CompDS/Ratings.csv

Books: https://an-utd-course.s3.us-west-1.amazonaws.com/CompDS/Books.csv
"""

# Imports
!pip install surprise

import re
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.neighbors import NearestNeighbors
from surprise.model_selection import GridSearchCV
from surprise import BaselineOnly
from surprise import SVD, KNNBasic, KNNBaseline
from surprise import Dataset, Reader
from surprise import accuracy
from surprise.model_selection import cross_validate, KFold
from tqdm import tqdm

# Read data into pandas dataframes
ratings = pd.read_csv('https://an-utd-course.s3.us-west-1.amazonaws.com/CompDS/Ratings.csv')
books = pd.read_csv('https://an-utd-course.s3.us-west-1.amazonaws.com/CompDS/Books.csv')

display(ratings)
display(books)

#ratings.dtypes

print("Number of Ratings (count of ratings, # of rating attributes):", ratings.shape)
print("Number of Books (count of books, # of book attributes):", books.shape)

print(ratings.isna().sum())
print(books.isna().sum())

ratings = ratings.dropna()
books = books.dropna()

print(ratings.isna().sum())
print(books.isna().sum())

print(ratings.shape)
print(books.shape)

# Merge CSV
df = books.merge(ratings, on = 'ISBN')
#test = df.loc[df['ISBN'] == '0786222743', :] #Check Results
#print(test['Book-Rating'])

def clean(title):
    return str(title).title().strip()

df['Book-Title'] = df['Book-Title'].apply(clean)
### This is to decrease the sample size and and include most popular books
df = df[df['User-ID'].map(df['User-ID'].value_counts()) > 150]
df = df[df['Book-Title'].map(df['Book-Title'].value_counts()) > 75]
df = df.reset_index(drop = True)

def top10(df):
  # Create indexes for each variable
  rating0 = df.groupby(['Book-Title']).count()['Book-Rating'].reset_index()
  rating_final = df.groupby('Book-Title')['Book-Rating'].mean().reset_index()
  isbn = df.groupby('Book-Title')['ISBN'].max().reset_index()

  # Rename values
  rating0.rename(columns = {'Book-Rating' : 'Count-Rating'}, inplace = True)
  rating_final.rename(columns = {'Book-Rating' : 'Rating-Avg'}, inplace = True)
  isbn.rename(columns = {'Book-Rating' : 'ISBN'}, inplace = True)

  # Merge
  book = rating0.merge(rating_final, on = 'Book-Title').merge(isbn, on = 'Book-Title')

  rate1 = book['Rating-Avg'].mean()
  count1 = book['Count-Rating'].quantile()

  # Filter by those with adequate ratings
  book = book[book['Count-Rating'] >= count1]
  book = book.sort_values(by = 'Rating-Avg', ascending = False)

  return book[['ISBN', 'Book-Title', 'Rating-Avg', 'Count-Rating']].reset_index(drop = True).head(10)

# Top 10 books have received the highest count of ratings
display(top10(df))

# Create a custom dataset using the surprise library
def get_subset(df, number):
    rids = np.arange(df.shape[0])
    np.random.shuffle(rids)
    df_subset = df.iloc[rids[:number], :].copy()
    return df_subset

# Subset data
df_ratings_1000 = get_subset(ratings, 1000)
df_df1_100 = get_subset(books, 100)

# Surprise reader
reader = Reader(rating_scale = (0, 10))

# Loader
ratings1 = Dataset.load_from_df(df_ratings_1000[['User-ID', 'ISBN', 'Book-Rating']], reader)

dataset = ratings1.build_full_trainset()
print('Number of users: ', dataset.n_users, '\n')
print('Number of items: ', dataset.n_items)

"""##### Choose a book at random and use the KNNBasic algorithm to find out its 10 closest neighbors. Do the results make sense?
After comparing and researching, the results do make sense and the books are connected.

"""

# Create pivot table
df = df.drop_duplicates(['User-ID', 'Book-Title'])
df_pivot = df.pivot(index = 'Book-Title', columns = 'User-ID', values = 'Book-Rating').fillna(0)
df_matrix = csr_matrix(df_pivot.values)

# Use KNN
model_knn = NearestNeighbors(metric = 'cosine', algorithm = 'brute')
model_knn.fit(df_matrix)
query = np.random.choice(df_pivot.shape[0])
distances, indices = model_knn.kneighbors(df_pivot.iloc[query, :].values.reshape(1, -1), n_neighbors = 11)

# Find the 10 closest books
for i in range(0, len(distances.flatten())):
    if i == 0:
        print('10 Nearest Neighbors for {0}:\n'.format(df_pivot.index[query]))
    else:
        print('{0}. {1}'.format(i, df_pivot.index[indices.flatten()[i]]))

mark = []

# Determine if there are significant differences from each algorithm
for algo in [SVD(), KNNBaseline(), BaselineOnly()]:
    # CV
    results = cross_validate(algo, ratings1, measures = ['RMSE'], cv = 10, verbose = False)
    # Append and receive results
    temp = pd.DataFrame.from_dict(results).mean(axis = 0)
    temp = temp.append(pd.Series([str(algo).split(' ')[0].split('.')[-1]], index = ['Algorithm']))
    mark.append(temp)

pd.DataFrame(mark).set_index('Algorithm').sort_values('test_rmse')

# SVD GridSearch
param_grid = {'n_epochs': [10, 15], 'lr_all': [0.001, 0.005],
              'reg_all': [0.4, 0.6]}
gs = GridSearchCV(SVD, param_grid, measures = ['rmse'], cv = 10)
gs.fit(ratings1)

# SVD RMSE Score
print(gs.best_score['rmse'])
print(gs.best_params['rmse'])

# KNN GridSearch
param_grid = {'n_epochs': [10, 15],
              'lr_all': [0.001, 0.005],
              'reg_all': [0.4, 0.6]}
gs = GridSearchCV(KNNBaseline, param_grid, measures = ['rmse'], cv = 10)
gs.fit(ratings1)

# KNN RMSE Score
print(gs.best_score['rmse'])
print(gs.best_params['rmse'])

# ALS GridSearch
param_grid = {'bsl_options' : {'method' : ['als'],
                               'n_epochs' : [5, 10],
                               'lr_all': [0.002, 0.005],
                               'reg_all': [0.4, 0.6]}}
bsl_algo = BaselineOnly()
gs = GridSearchCV(BaselineOnly, param_grid, measures = ['rmse'], cv = 10)
gs.fit(ratings1)

# ALS RMSE Score
print(gs.best_score['rmse'])
print(gs.best_params['rmse'])

# SGD GridSearch
param_grid = {'bsl_options' : {'method' : ['sgd'],
                               'n_epochs' : [5, 10],
                               'lr_all': [0.002, 0.005],
                               'reg_all': [0.4, 0.6]}}
bsl_algo = BaselineOnly()
gs = GridSearchCV(BaselineOnly, param_grid, measures = ['rmse'], cv = 10)
gs.fit(ratings1)

# SGD RMSE Score
print(gs.best_score['rmse'])
print(gs.best_params['rmse'])
