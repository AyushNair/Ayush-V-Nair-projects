# -*- coding: utf-8 -*-

import json
import datetime
from argparse import ArgumentParser
import torch
import torch.nn.functional as F
import pickle
from tqdm import tqdm
import os


def fetch_past_k_days_unlabel_news(k, date2idx, post_date):
    assert k >= 1
    all_idx = []
    post_date = datetime.datetime.strptime(post_date, "%Y-%m-%d")
    for delta_date in range(1, k+1):
        target_date = (post_date + datetime.timedelta(
            days=-delta_date)).strftime("%Y-%m-%d")
        if target_date in date2idx:
            idx = date2idx[target_date]
        else:
            idx = []
            if k == 1:
                print(
                    "Post at {} don't have news at yesterday.".format(post_date))
        all_idx.extend(idx)
    return all_idx


def get_cosine(post, date2recent_news_idx, all_news_vec, post_vec, dataset, split_name, days):
    ranked_sims_in_n_days = []
    for i in tqdm(range(len(post))):
        date = post[i]['time'].split(" ")[0]
        news_idxs = date2recent_news_idx[date]
        news_vec = all_news_vec[news_idxs, :]
        cos_sims = torch.matmul(post_vec[i], news_vec.transpose(0, 1)).tolist()
        tup = zip(news_idxs, cos_sims)
        tup = sorted(tup, key=lambda x: x[1], reverse=True)
        ranked_sims_in_n_days.append(tup)
    output_dir = './data/{}'.format(dataset)
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, '{}_{}d.pkl'.format(split_name, days)), 'wb') as output:
        pickle.dump(ranked_sims_in_n_days, output)


if __name__ == "__main__":

    parser = ArgumentParser(description='get_env')
    parser.add_argument('--dataset', type=str, default="Chinese")
    parser.add_argument('--macro_env_days', type=int, default=3)
    args = parser.parse_args()

    dataset = args.dataset
    days = args.macro_env_days

    with open('../../dataset/{}/post/train.json'.format(dataset), 'r', encoding='utf-8') as source:
        train = json.load(source)
    with open('../../dataset/{}/post/val.json'.format(dataset), 'r', encoding='utf-8') as source:
        val = json.load(source)
    with open('../../dataset/{}/post/test.json'.format(dataset), 'r', encoding='utf-8') as source:
        test = json.load(source)
    with open('../../dataset/{}/news/news.json'.format(dataset), 'r', encoding='utf-8') as source:
        news = json.load(source)

    train_vec = pickle.load(open(
        '../SimCSE/data/{}/post/train_vecs_origin.pkl'.format(dataset), 'rb'))
    val_vec = pickle.load(open(
        '../SimCSE/data/{}/post/val_vecs_origin.pkl'.format(dataset), 'rb'))
    test_vec = pickle.load(open(
        '../SimCSE/data/{}/post/test_vecs_origin.pkl'.format(dataset), 'rb'))
    news_vec = pickle.load(open(
        '../SimCSE/data/{}/news/all_vecs_origin.pkl'.format(dataset), 'rb'))

    # L2 normalization
    train_vec = F.normalize(train_vec, dim=1)
    val_vec = F.normalize(val_vec, dim=1)
    test_vec = F.normalize(test_vec, dim=1)
    news_vec = F.normalize(news_vec, dim=1)

    date2idx = {}
    for i in range(len(news)):
        date = news[i]['time'].split(' ')[0]
        if date in date2idx:
            date2idx[date].append(i)
        else:
            date2idx[date] = []
            date2idx[date].append(i)

    all_post_dates = set()
    for dtst in [train, val, test]:
        for d in dtst:
            all_post_dates.add(d['time'].split(' ')[0])
    all_post_dates = sorted(list(all_post_dates))

    date2recent_news_idx = {}
    for d in all_post_dates:
        date2recent_news_idx[d] = fetch_past_k_days_unlabel_news(
            days, date2idx, d)

    get_cosine(train, date2recent_news_idx, news_vec,
               train_vec, dataset, 'train_data', days)
    get_cosine(val, date2recent_news_idx, news_vec,
               val_vec, dataset, 'val_data', days)
    get_cosine(test, date2recent_news_idx, news_vec,
               test_vec, dataset, 'test_data', days)
