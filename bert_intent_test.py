import numpy as np
import os
import platform
import tensorflow as tf
from keras.preprocessing.text import Tokenizer, text_to_word_sequence
from keras.preprocessing import sequence
from keras.utils.np_utils import to_categorical
from keras.layers import Dense, Embedding, Input, Concatenate, Flatten, MaxPooling1D, Lambda, GlobalAveragePooling1D, \
    Dropout, TimeDistributed, BatchNormalization, GlobalMaxPool1D, Bidirectional, LSTM
from keras import regularizers, optimizers
from keras.layers.core import Dense, Dropout, Activation
from keras.callbacks import ModelCheckpoint
from keras.models import Model, Sequential
from keras.utils import plot_model
# from keras_contrib.layers import CRF
# from matplotlib import pyplot
# from sklearn import metrics
from get_ip import get_host_ip
import seaborn as sns
import shutil

from keras.initializers import Constant
import keras.backend.tensorflow_backend as KTF

if platform.system() == "Darwin":
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
    print('MAC')
if platform.system() == "Linux":
    print("Linux")
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True  # 不全部占满显存, 按需分配
    sess = tf.Session(config=config)
    KTF.set_session(sess)
    print("h1")

base_dir = os.path.dirname(__file__)
emb_dim = 300
max_sequence_length = 50
max_features = 20000
batch_size = 16

middle = '/data/xiaoyichao/data/atis'

learning_rate=0.25e-4
epochs = 300



def load_sentences(path):
    """返回的的是文本的list嵌套list"""
    with open(path, 'r') as f:
        lines = f.read().split('\n')
    # 去掉最后一行的空list
    lines = [x for x in lines if x]
    sentences = []
    for sentence in lines:
        # print(sentence)
        # 作用一样，一个是自己写的，一个是自带的API
        sent_tmp = text_to_word_sequence(sentence, filters='!"#$%&()*+,-./:;<=>?@[\]^_`{|}~ ', split=' ', lower=True)
        # sent_tmp = sentence.split(' ')
        sentences.append(sent_tmp)
    return sentences


def load_train_labels(path):
    with open(path, 'r') as f:
        lines = f.read().split('\n')
    # 去掉最后一行的空list
    y_intent = [x for x in lines if x]
    # 取第一个标签作为这个数据的标签
    # y_intent = [x.split("#")[0] for x in y_intent ]

    label_set_trian = set(y_intent)
    label_set = set(y_intent)
    if ('atis' in middle) or (middle == 'new_slur_alltest'):
        label_set.add('unknown')
        print("add an unknown class")
    class_num = len(label_set)
    labels_index = {}
    for name in label_set:
        label_id = len(labels_index)
        labels_index[name] = label_id

    y_train_label = []
    for label in y_intent:
        y_id = labels_index[label]
        y_train_label.append(y_id)

    y_train_label = to_categorical(np.asarray(y_train_label), num_classes=class_num)

    print(class_num,labels_index)
    return y_train_label, class_num, labels_index, label_set_trian


def load_test_labels(labels_index, label_set_trian, path):
    "根据给的index，得初valid和test的label 的 ndarray"
    with open(path, 'r') as f:
        lines = f.read().split('\n')
    # 去掉最后一行的空list
    y_intent = [x for x in lines if x]
    # 取第一个标签作为这个数据的标签
    # y_intent = [x.split("#")[0] for x in y_intent ]

    class_num = len(labels_index)

    y_intent_seq = []
    for label in y_intent:
        if (label in label_set_trian):
            y_id = labels_index[label]
        else:
            y_id = labels_index['unknown']

        y_intent_seq.append(y_id)

    y_intent_seq = to_categorical(np.asarray(y_intent_seq), num_classes=class_num)

    return y_intent_seq


# 根据上边的函数，对输入和意图标签进行处理

# 对输入的文本进行处理
train_sentence_seq = load_sentences(os.path.join(base_dir, middle, 'train/seq.in'))
valid_sentence_seq = load_sentences(os.path.join(base_dir, middle, 'valid/seq.in'))
test_sentence_seq = load_sentences(os.path.join(base_dir, middle, 'test/seq.in'))



# token = Tokenizer(num_words=max_features)
token = Tokenizer(num_words=max_features, filters='', oov_token='<UNK>')
token.fit_on_texts([utterance for utterance in train_sentence_seq])

# 文本数值化
x_train_dia_list = token.texts_to_sequences(train_sentence_seq)
x_valid_dia_list = token.texts_to_sequences(valid_sentence_seq)
x_test_dia_list = token.texts_to_sequences(test_sentence_seq)
word_index = token.word_index
# print(word_index)

# 数值化之后padding 过程
x_train_dia_list = sequence.pad_sequences(x_train_dia_list, maxlen=max_sequence_length)
x_valid_dia_list = sequence.pad_sequences(x_valid_dia_list, maxlen=max_sequence_length)
x_test_dia_list = sequence.pad_sequences(x_test_dia_list, maxlen=max_sequence_length)

# 对意图标签进行处理
y_train_label, class_num, labels_index, label_set_trian = load_train_labels(
    os.path.join(base_dir, middle, 'train/label'))
y_valid_label = load_test_labels(labels_index, label_set_trian, os.path.join(base_dir, middle, 'valid/label'))
y_test_label = load_test_labels(labels_index, label_set_trian, os.path.join(base_dir, middle, 'test/label'))


# 意图标签和文本信息都处理好了


# prepare embedding matrix
num_words = min(max_features, len(word_index)) + 1
embedding_matrix = np.zeros((num_words, glove_emb_dim))
for word, i in word_index.items():
    if i > max_features:
        continue
    embedding_vector = embeddings_index.get(word)
    if embedding_vector is not None:
        # words not found in embedding index will be all-zeros.
        embedding_matrix[i] = embedding_vector

# load pre-trained word embeddings into an Embedding layer
# note that we set trainable = False so as to keep the embeddings fixed
glove_embedding_layer = Embedding(num_words,
                                  glove_emb_dim,
                                  embeddings_initializer=Constant(embedding_matrix),
                                  input_length=max_sequence_length,
                                  trainable=True, name='glove_embedding', mask_zero=True)

# 构建model

