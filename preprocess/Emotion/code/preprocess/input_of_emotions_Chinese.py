import os
import json
from tqdm import tqdm
import time
import numpy as np
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'emotion')))
import extract_emotion_ch
# import extract_emotion_en



datasets_ch = ['Chinese']
datasets_en = ['English']

for dataset in datasets_ch:
    print('\n\n{} [{}]\tProcessing the dataset: {} {}\n'.format(
        '-'*20, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()), dataset, '-'*20))

    save_dir = '../../data'
    os.makedirs(save_dir, exist_ok=True)

    if dataset in datasets_ch:
        extract_pkg = extract_emotion_ch
    else:
        # extract_pkg = extract_emotion_en
        pass

    data_dir = os.path.join('../../../../dataset', dataset, 'post')
    output_dir = os.path.join(save_dir, dataset)
    os.makedirs(output_dir, exist_ok=True)
    emotion_dir = os.path.join(output_dir, 'emotions')
    os.makedirs(emotion_dir, exist_ok=True)

    split_datasets = []
    for split in ['train', 'val', 'test']:
        with open(os.path.join(data_dir, '{}.json'.format(split)), 'r', encoding='utf-8') as source:
            split_datasets.append(json.load(source))
    split_datasets = dict(zip(['train', 'val', 'test'], split_datasets))

    for t, pieces in split_datasets.items():
        emotion_file = os.path.join(emotion_dir, '{}.npy'.format(t))
        words_file = os.path.join(output_dir, '{}.json'.format(t))
        if os.path.exists(emotion_file):
            continue

        if os.path.exists(words_file):
            with open(words_file, 'r', encoding='utf-8') as source:
                pieces = json.load(source)

        # words cutting
        if pieces and 'content_words' not in pieces[0]:
            print('[{}]\tWords Cutting...'.format(
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())))
            for p in tqdm(pieces):
                if 'words' in p:
                    del p['words']
                p['content_words'] = extract_pkg.cut_words_from_text(
                    p['content'])
                # p['comments_words'] = [extract_pkg.cut_words_from_text(
                #     com) for com in p['comments']]
            with open(words_file, 'w', encoding='utf-8') as f:
                json.dump(pieces, f, indent=4, ensure_ascii=False)

        if not pieces:
            np.save(emotion_file, np.empty((0, 0), dtype=float))
            continue

        # Only publisher emotion
        emotion_arr = [extract_pkg.extract_publisher_emotion(
            p['content'], p['content_words']) for p in tqdm(pieces)]
        emotion_arr = np.array(emotion_arr)
        print('{} dataset: got a {} emotion arr'.format(t, emotion_arr.shape))
        np.save(emotion_file, emotion_arr)
