"""Training a face recognizer with TensorFlow based on the FaceNet paper
FaceNet: A Unified Embedding for Face Recognition and Clustering: http://arxiv.org/abs/1503.03832
"""
#   MIT License
#  Copyright (c) 2021. TranPhuongNam,DaoLeBaoThoa,NguyenDiemUyenPhuong
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.

import tensorflow as tf
import os
import sys
import argparse


def scheduler(epoch,lr):
    if epoch < 70:
        return lr
    elif epoch < 100:
        ret = lr/1.01
        return ret
    else:
        ret = lr/1.001
        return ret

def main(args):

    # Get number of classes for training
    num_classes = len(os.listdir(args.dataset_path))

    # Create data train and validation from directory
    datagen_train = tf.keras.preprocessing.image_dataset_from_directory(args.dataset_path, batch_size=args.batch_size,seed=args.seed_random,
                                                                labels='inferred', label_mode='categorical',image_size=(args.image_size,args.image_size),
                                                                validation_split=args.validation_split,subset="training")
    datagen_val   = tf.keras.preprocessing.image_dataset_from_directory(args.dataset_path, batch_size=args.batch_size,seed=args.seed_random,
                                                                labels='inferred', label_mode='categorical', image_size=(args.image_size, args.image_size),
                                                                validation_split=args.validation_split, subset="validation")

    # Create facenet model with L2 embeddings
    model = tf.keras.models.load_model(args.model_path)
    L2_normalization = tf.keras.layers.Lambda(lambda x: tf.math.l2_normalize(x, axis = 1), name='L2_normalization')(model.output)
    predictions = tf.keras.layers.Dense(num_classes, activation='softmax',name='Predictions')(L2_normalization)
    model = tf.keras.models.Model(inputs=[model.input], outputs=[predictions])
    out_model=os.path.join(os.path.split(args.model_path)[0],'softmax_keras_facenet_model.h5')
    model.save(out_model)

    # Rescaling dataset
    AUTOTUNE = tf.data.AUTOTUNE

    train_ds = datagen_train.cache().shuffle(1000).prefetch(buffer_size=AUTOTUNE)
    val_ds = datagen_val.cache().prefetch(buffer_size=AUTOTUNE)

    normalization_layer = tf.keras.layers.experimental.preprocessing.Rescaling(1./255)
    normalized_ds = train_ds.map(lambda x, y: (normalization_layer(x), y))
    normalized_vds= val_ds.map(lambda x, y: (normalization_layer(x), y))

    # Create checkpoint
    if args.model_checkpoint_path is not None:
        MODEL_CHECKPOINT_PATH=os.path.join(args.model_checkpoint_path,'model_softmax_checkpoint.h5')
    else:
        MODEL_CHECKPOINT_PATH=os.path.join(os.path.split(args.model_path)[0],'model_softmax_checkpoint.h5')
    mcp = tf.keras.callbacks.ModelCheckpoint(MODEL_CHECKPOINT_PATH, monitor="val_accuracy",
                                             save_best_only=True, save_weights_only=True)

    lr_decrease = tf.keras.callbacks.LearningRateScheduler(scheduler)

    if args.model_logs_path is not None:
        tensorboard_callback = tf.keras.callbacks.TensorBoard(log_dir=args.model_logs_path, histogram_freq=1)
        callbacks=[mcp,lr_decrease,tensorboard_callback]
    else:
        callbacks=[mcp,lr_decrease]

    # Compile model
    model.compile(optimizer=tf.keras.optimizers.Adam(args.learning_rate),loss='categorical_crossentropy',metrics=['accuracy'])

    # Training
    model.fit(normalized_ds,validation_data=normalized_vds,validation_freq=args.validation_freq, epochs=args.epochs,callbacks=callbacks)


def parse_arguments(argv):
    parser = argparse.ArgumentParser()

    parser.add_argument('model_path', type=str,
                        help='Path to the model keras (inception resnet v1) (.h5 file)')

    parser.add_argument('dataset_path', type=str,
                        help='Path to the dataset directory')

    parser.add_argument('--model_checkpoint_path', type=str,
                        help='Path to the checkpoint directory', default=None)

    parser.add_argument('--image_size', type=int,
                        help='Image size of Facenet input', default=160)

    parser.add_argument('--model_logs_path', type=str,
                        help='Path to the logs directory', default=None)

    parser.add_argument('--learning_rate', type=float,
                        help='Default is 0.001', default=0.001)

    parser.add_argument('--epochs', type=int,
                        help='Default is 90', default=90)

    parser.add_argument('--batch_size', type=int,
                        help='Default is 32', default=32)

    parser.add_argument('--seed_random', type=int,
                        help='Default is 123', default=123)

    parser.add_argument('--validation_split', type=float,
                        help='Default is 0.1', default=0.1)

    parser.add_argument('--validation_freq', type=int,
                        help='Default is 1', default=1)


    return parser.parse_args(argv)


if __name__ == '__main__':
    main(parse_arguments(sys.argv[1:]))
